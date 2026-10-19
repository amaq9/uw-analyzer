"use client";

import { SnapshotViewer } from "@/components/case/research-tab";
import { type ClaimRecord, type TabProps } from "@/components/case/types";
import { useLoad } from "@/components/use-api";
import { api } from "@/lib/api/client";
import { dateOnly, dateTime, readable, shorten } from "@/lib/format";

/** The classification as a person reads it. An interpretation here is the written rules applied to facts. */
const CLASS_WORD: Record<string, string> = { INTERPRETATION: "Rule-based assessment", INFERENCE: "Inference" };

function EvidenceList({ caseId, claim, token }: Readonly<{ caseId: string; claim: ClaimRecord; token: string }>) {
  return (
    <ul className="ws-list">
      {claim.links.map((link) => (
        <li key={link.id}>
          <strong>{readable(link.relation)}</strong>: {link.evidence.title}
          <p className="ws-muted">
            Source: {link.evidence.origin} · {readable(link.evidence.source_class)} (
            {link.evidence.source_class_basis === "registry" ? "class from the source registry" : "class declared by the author"}
            ){link.evidence.discovery_only ? " · leads only" : ""}
            <br />
            Accessed {dateTime(link.evidence.accessed_at)} via {readable(link.evidence.kind).toLowerCase()} ·{" "}
            {link.evidence.evidence_type === "FINANCIAL" ? "figures for" : "as of"} {dateOnly(link.evidence.event_on)} ·{" "}
            {link.evidence.published_on ? `published ${dateOnly(link.evidence.published_on)}` : "publication date not recorded"}
          </p>
          <blockquote className="ws-quote">{link.evidence.excerpt}</blockquote>
          {link.evidence.url && (
            <a href={link.evidence.url} rel="noreferrer" target="_blank">
              Open the web source
            </a>
          )}
          {link.evidence.provenance_ref?.startsWith("snapshot://") && (
            <SnapshotViewer caseId={caseId} reference={link.evidence.provenance_ref} token={token} />
          )}
        </li>
      ))}
    </ul>
  );
}

export function EvidenceTab({ caseId, currency, token }: TabProps) {
  const base = `/api/v1/cases/${encodeURIComponent(caseId)}/claims`;
  const claims = useLoad((t, signal) => api<ClaimRecord[]>(t, "GET", base, undefined, signal), [caseId]);
  const list = claims.data ?? [];
  const byId = new Map(list.map((claim) => [claim.id, claim]));
  const basisClaims = (claim: ClaimRecord) =>
    (claim.basis_claim_ids ?? []).flatMap((id) => {
      const found = byId.get(id);
      return found ? [found] : [];
    });

  return (
    <div className="ws-stack">
      <section className="ws-card">
        <h2>Evidence and claims</h2>
        <p>
          Each finding is a claim. <strong>Access</strong> (when and how the source was read) and{" "}
          <strong>verification</strong> (what the evidence supports) are shown separately and are never merged. The
          verification status is worked out by fixed rules from the linked evidence. Nobody can type it in, and neither can
          the analyst.
        </p>
      </section>

      {list.length === 0 && (
        <section className="ws-card">
          <p>No claim has been recorded yet. Ask for the case to be analysed and the findings appear here.</p>
        </section>
      )}

      {list.map((claim) => (
        <section className="ws-card" key={claim.id}>
          <p className="ws-pill-row">
            <span className="ws-pill">{CLASS_WORD[claim.classification] ?? readable(claim.classification)}</span>
            <span className="ws-pill">{claim.material ? "Material" : "Not material"}</span>
            {claim.adverse && <span className="ws-pill">Adverse</span>}
            {claim.category && <span className="ws-pill">{readable(claim.category)}</span>}
          </p>
          <p className="ws-claim-text">{shorten(claim.text, currency)}</p>
          <div className="ws-split">
            <div>
              <h4>Verification</h4>
              <p>
                <strong>{readable(claim.verification.status)}</strong>
                {claim.freshness ? ` · evidence is ${readable(claim.freshness).toLowerCase()}` : ""}
              </p>
              <ul className="ws-bullets">
                {claim.verification.reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
                {claim.verification.needs.map((need) => (
                  <li key={need}>Needed: {need}</li>
                ))}
              </ul>
              {claim.verification.conflict && (
                <p className="ws-note">Reliable sources disagree. See Review items.</p>
              )}
            </div>
            <div>
              <h4>Linked evidence and access</h4>
              {claim.links.length === 0 && basisClaims(claim).length === 0 && <p>No evidence is linked.</p>}
              <EvidenceList caseId={caseId} claim={claim} token={token} />
              {basisClaims(claim).length > 0 && (
                <>
                  <h4>Rests on these facts</h4>
                  <ul className="ws-list">
                    {basisClaims(claim).map((basis) => (
                      <li key={basis.id}>
                        <p className="ws-claim-text">{shorten(basis.text, currency)}</p>
                        <p className="ws-muted">
                          Verification: <strong>{readable(basis.verification.status)}</strong>
                        </p>
                        {basis.links.length === 0 && <p className="ws-muted">No evidence is linked to this fact.</p>}
                        <EvidenceList caseId={caseId} claim={basis} token={token} />
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          </div>
        </section>
      ))}
    </div>
  );
}
