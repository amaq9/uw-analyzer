"use client";

import { useState } from "react";

import {
  type ReportPreview,
  type ReportRecord,
  type ReportSummary,
  type TabProps,
  can,
} from "@/components/case/types";
import { ActionError, useAction, useLoad } from "@/components/use-api";
import { api } from "@/lib/api/client";
import { dateOnly, dateTime, readable, shorten } from "@/lib/format";

type Content = ReportPreview["content"];

function ReportBody({ content: raw, currency }: Readonly<{ content: Content; currency?: string | null }>) {
  // An older API may omit newer lists; show them as empty instead of failing.
  const content = { ...raw, financials_reviewed: raw.financials_reviewed ?? [], conflicts: raw.conflicts ?? [], unverified_claims: raw.unverified_claims ?? [], material_findings: raw.material_findings ?? [], information_gaps: raw.information_gaps ?? [], limitations: raw.limitations ?? [], verification_log: raw.verification_log ?? [] };
  const counts = content.counts;
  return (
    <div className="ws-stack">
      <p className="ws-note">{content.notice}</p>

      <section className="ws-card">
        <h3>Financial statements reviewed</h3>
        {content.financials_reviewed.length === 0 ? (
          <p>No financial statements were reviewed.</p>
        ) : (
          <ul className="ws-list">
            {content.financials_reviewed.map((row) => (
              <li key={row.evidence_id}>
                <strong>{row.title}</strong>
                <p className="ws-muted">
                  Figures for the period ending {dateOnly(row.period_end)} · published {dateOnly(row.published_on)} · read{" "}
                  {dateTime(row.accessed_at)} · {row.origin} ({readable(row.source_class)},{" "}
                  {row.source_class_basis === "registry" ? "class from registry" : "class declared by the author"})
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="ws-card">
        <h3>Evidence confidence: {readable(content.evidence_confidence.level)}</h3>
        <ul className="ws-bullets">
          {content.evidence_confidence.explanations.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
        <p className="ws-muted">
          This describes how well the evidence supports the findings. It is not a score or a rating.
        </p>
      </section>

      <section className="ws-card">
        <h3>Sources the research tried</h3>
        {content.verification_log.length === 0 ? (
          <p>No research run has finished for this case.</p>
        ) : (
          <div className="ws-table-wrap">
            <table className="ws-table">
              <thead>
                <tr>
                  <th>Area</th>
                  <th>Source</th>
                  <th>State</th>
                  <th>Accessed</th>
                  <th>Note</th>
                </tr>
              </thead>
              <tbody>
                {content.verification_log.map((row, index) => (
                  <tr key={`${row.category}-${row.source_key}-${index}`}>
                    <td>{readable(row.category)}</td>
                    <td>{row.source_name ?? "No source registered"}</td>
                    <td>{readable(row.state)}</td>
                    <td>{row.accessed ? "Yes" : "No"}</td>
                    <td>{row.reason ?? ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p>{content.adverse_search_statement}</p>
      </section>

      <section className="ws-card">
        <h3>Material findings</h3>
        <ul className="ws-list">
          {content.material_findings.map((claim) => (
            <li key={claim.claim_id}>
              {shorten(claim.text, currency)}
              <p className="ws-muted">
                Verification: {readable(claim.verification_status)}
                {claim.freshness ? ` · ${readable(claim.freshness)} evidence` : ""}
                {claim.conflict ? " · sources disagree" : ""} · {claim.evidence_ids.length} evidence item(s) linked
              </p>
            </li>
          ))}
        </ul>
        {content.unverified_claims.length > 0 && (
          <>
            <h4>Not fully verified</h4>
            <ul className="ws-list">
              {content.unverified_claims.map((claim) => (
                <li key={claim.claim_id}>
                  {claim.text}
                  <p className="ws-muted">{readable(claim.verification_status)}</p>
                </li>
              ))}
            </ul>
          </>
        )}
        {content.conflicts.length > 0 && (
          <>
            <h4>Conflicts</h4>
            <ul className="ws-list">
              {content.conflicts.map((item) => (
                <li key={item.escalation_id}>
                  {item.description}
                  <p className="ws-muted">
                    {readable(item.state)}
                    {item.resolution_outcome ? ` · ${readable(item.resolution_outcome)}` : ""}
                  </p>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>

      <section className="ws-card">
        <h3>Information gaps and limitations</h3>
        <ul className="ws-bullets">
          {content.information_gaps.map((gap) => (
            <li key={gap}>{gap}</li>
          ))}
          {content.limitations.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </section>

      <section className="ws-card">
        <h3>Final statement</h3>
        <p>{content.final_statement}</p>
        <p className="ws-muted">
          Connector sources accessed: {counts.connector_sources_accessed} · documents reviewed: {counts.documents_reviewed} ·
          web sources recorded by the analyst: {counts.web_sources_recorded} · material findings verified:{" "}
          {counts.verified_material_findings} of {counts.material_claims} · unavailable sources:{" "}
          {counts.unavailable_sources} · information gaps: {counts.information_gaps} · items awaiting review:{" "}
          {counts.open_escalations}
        </p>
      </section>
    </div>
  );
}

export function ReportTab({ caseId, currency, onChanged, permissions, token }: TabProps) {
  const base = `/api/v1/cases/${encodeURIComponent(caseId)}`;
  const preview = useLoad((t, signal) => api<ReportPreview>(t, "GET", `${base}/report-preview`, undefined, signal), [caseId]);
  const history = useLoad((t, signal) => api<ReportSummary[]>(t, "GET", `${base}/reports`, undefined, signal), [caseId]);
  const [shownVersion, setShownVersion] = useState<number>();
  const stored = useLoad(
    (t, signal) =>
      shownVersion ? api<ReportRecord>(t, "GET", `${base}/reports/${shownVersion}`, undefined, signal) : Promise.resolve(undefined),
    [caseId, shownVersion],
  );
  const complete = useAction();
  const [note, setNote] = useState("");
  const canComplete = can(permissions, "report:complete");
  const p = preview.data;

  async function completeReport() {
    const done = await complete.run(() =>
      api<ReportRecord>(token, "POST", `${base}/reports`, note.trim() ? { note: note.trim() } : {}),
    );
    if (done) {
      setNote("");
      setShownVersion(done.version);
      history.reload();
      preview.reload();
      onChanged();
    }
  }

  return (
    <div className="ws-stack">
      <section className="ws-card">
        <h2>Research report</h2>
        <p>
          The report restates what the case&apos;s evidence supports. It contains no recommendation or decision. Completing
          it stores a permanent version; changes later make a new version, and earlier ones are never altered.
        </p>
      </section>

      {p && (
        <section className="ws-card">
          <h3>Completion checks</h3>
          <ul className="ws-checks">
            {p.gates.map((gate) => (
              <li key={gate.code}>
                <span aria-hidden="true">{gate.passed ? "✔" : "✘"}</span> {gate.message}
              </li>
            ))}
          </ul>
          {canComplete ? (
            <div className="ws-form">
              <label className="ws-field">
                Note for this version (optional)
                <input onChange={(event) => setNote(event.target.value)} value={note} />
              </label>
              <button className="ws-button primary" disabled={!p.can_complete || complete.busy} onClick={completeReport} type="button">
                Complete the report
              </button>
              {!p.can_complete && <p className="ws-muted">Every check must pass before the report can be completed.</p>}
              <ActionError error={complete.error} />
            </div>
          ) : (
            <p className="ws-muted">Your role cannot complete the report.</p>
          )}
        </section>
      )}

      {(history.data ?? []).length > 0 && (
        <section className="ws-card">
          <h3>Version history</h3>
          <ul className="ws-list">
            {(history.data ?? []).map((version) => (
              <li key={version.id}>
                <button className="ws-link" onClick={() => setShownVersion(version.version)} type="button">
                  Version {version.version}
                </button>{" "}
                · {dateTime(version.created_at)} · {version.created_by}
                {version.note ? ` · ${version.note}` : ""}
                <small className="ws-muted"> · hash {version.content_hash.slice(0, 12)}…</small>
              </li>
            ))}
          </ul>
        </section>
      )}

      {shownVersion && stored.data ? (
        <>
          <p className="ws-note">
            Showing stored version {stored.data.version}, completed {dateTime(stored.data.created_at)}. Integrity check:{" "}
            {stored.data.integrity_verified ? "the stored text matches its recorded hash" : "MISMATCH, do not rely on this version"}.
          </p>
          <ReportBody content={stored.data.content} currency={currency} />
        </>
      ) : (
        p && (
          <>
            <p className="ws-note">Live preview as of {dateTime(p.content.as_of)}. Nothing here is saved until you complete the report.</p>
            <ReportBody content={p.content} currency={currency} />
          </>
        )
      )}
    </div>
  );
}
