"use client";

import Link from "next/link";

import { DecisionForm, DecisionSummary } from "@/components/case/decision-form";
import { type DecisionRecord, type DraftRecord, type TabProps, can } from "@/components/case/types";
import { useLoad } from "@/components/use-api";
import { ApiRequestError, api } from "@/lib/api/client";
import { dateTime, money, readable } from "@/lib/format";

async function loadDecision(token: string, base: string, draftId: string, signal: AbortSignal) {
  try {
    return await api<DecisionRecord>(token, "GET", `${base}/${draftId}/decision`, undefined, signal);
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 404) return null;
    throw error;
  }
}

export function RecommendationTab({ caseId, onChanged, permissions, token }: TabProps) {
  const base = `/api/v1/cases/${encodeURIComponent(caseId)}/draft-recommendations`;
  const drafts = useLoad((t, signal) => api<DraftRecord[]>(t, "GET", base, undefined, signal), [caseId]);
  const list = drafts.data ?? [];
  const latest = list[0];
  const decision = useLoad(
    (t, signal) => (latest ? loadDecision(t, base, latest.id, signal) : Promise.resolve(null)),
    [caseId, latest?.id],
  );
  const canDecide = can(permissions, "decision:record");

  return (
    <div className="ws-stack">
      <section className="ws-card">
        <h2>Draft recommendation for the underwriter</h2>
        <p>
          A draft is prepared from the evidence by the analyst, then the approved test policy (v1.0) is applied by the system.
          It is a recommendation only. <strong>Not a decision.</strong> Only your recorded decision below is a decision.
        </p>
      </section>

      {!latest && (
        <section className="ws-card">
          <p>No draft has been prepared yet. Ask for the case to be analysed.</p>
        </section>
      )}

      {latest && (
        <section className="ws-card">
          <p className="eyebrow">Draft recommendation for the underwriter. Not a decision.</p>
          <h3>
            Version {latest.version} · prepared {dateTime(latest.created_at)}
          </h3>
          <dl className="ws-facts">
            <div>
              <dt>Requested amount</dt>
              <dd>{money(latest.requested_amount, latest.requested_currency)}</dd>
            </div>
            <div>
              <dt>Draft outcome</dt>
              <dd>
                {latest.outcome === "APPROVE"
                  ? `Approve ${money(latest.recommended_amount, latest.requested_currency)} (${readable(latest.band).toLowerCase()})`
                  : "Decline"}
              </dd>
            </div>
            <div>
              <dt>Analyst&apos;s proposed amount</dt>
              <dd>{money(latest.ai_proposed_amount, latest.requested_currency)}</dd>
            </div>
            <div>
              <dt>Policy version</dt>
              <dd>{latest.policy_version}</dd>
            </div>
          </dl>
          <p>{latest.summary}</p>
          <p>
            <Link className="inline-action" href={`/cases/${caseId}/recommendations/${latest.id}`}>
              Open the full draft with reasons and sources
            </Link>
          </p>
          {latest.information_gaps.length > 0 && (
            <>
              <h4>Information gaps</h4>
              <ul className="ws-bullets">
                {latest.information_gaps.map((gap) => (
                  <li key={gap}>{gap}</li>
                ))}
              </ul>
            </>
          )}
          <p className="ws-muted">{latest.limitations.join(" ")}</p>
        </section>
      )}

      {latest && decision.data && <DecisionSummary decision={decision.data} />}
      {latest && decision.data === null && canDecide && (
        <DecisionForm
          base={base}
          draft={latest}
          onDone={() => {
            decision.reload();
            onChanged();
          }}
          token={token}
        />
      )}
      {latest && decision.data === null && !canDecide && (
        <section className="ws-card">
          <p>No decision has been recorded. Your role cannot record one.</p>
        </section>
      )}

      {list.length > 1 && (
        <section className="ws-card">
          <h3>Earlier drafts</h3>
          <ul className="ws-list">
            {list.slice(1).map((draft) => (
              <li key={draft.id}>
                <Link className="ws-link" href={`/cases/${caseId}/recommendations/${draft.id}`}>
                  Version {draft.version} · {dateTime(draft.created_at)}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
