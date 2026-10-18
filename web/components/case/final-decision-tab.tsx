"use client";

import { outcomeHeadline, TestPill } from "@/components/case/draft-hero";
import { loadDecision } from "@/components/case/decision-data";
import type { DraftRecord, TabProps } from "@/components/case/types";
import { useLoad } from "@/components/use-api";
import { api, type CaseRecord } from "@/lib/api/client";
import { dateTime, money, readable, shorten } from "@/lib/format";

type Props = TabProps & { record: CaseRecord };

/** One printable page: the underwriter's recorded decision, set beside the draft it answers. */
export function FinalDecisionTab({ caseId, record }: Props) {
  const base = `/api/v1/cases/${encodeURIComponent(caseId)}/draft-recommendations`;
  const drafts = useLoad((t, signal) => api<DraftRecord[]>(t, "GET", base, undefined, signal), [caseId]);
  const draft = drafts.data?.[0];
  const decision = useLoad(
    (t, signal) => (draft ? loadDecision(t, base, draft.id, signal) : Promise.resolve(null)),
    [caseId, draft?.id],
  );
  const decided = decision.data;

  if (drafts.loading || decision.loading) return <p className="ws-muted">Loading the final decision…</p>;

  if (!draft || !decided) {
    return (
      <section className="ws-card">
        <p className="eyebrow">Final decision</p>
        <h3>No decision has been recorded yet</h3>
        <p>
          {draft
            ? "Open the Draft recommendation tab and complete Step 3, Your decision. The one-page report appears here as soon as you record it."
            : "Prepare a draft on the Draft recommendation tab first, then record your decision there."}
        </p>
      </section>
    );
  }

  const currency = draft.requested_currency;
  const name = record.legal_name ?? record.trading_name ?? "Unnamed case";
  const final =
    decided.final_outcome === "APPROVE"
      ? `Approve ${money(decided.final_amount, decided.currency)}`
      : decided.final_outcome === "DECLINE"
        ? "Decline"
        : "No outcome recorded (draft set aside)";
  const gaps = [...new Set(draft.information_gaps)];

  return (
    <div className="ws-stack">
      <div className="final-actions no-print">
        <p className="ws-muted">One page. Use the button, then choose “Save as PDF” as the printer to keep a copy.</p>
        <button className="ws-button primary" onClick={() => window.print()} type="button">
          Print or save as PDF
        </button>
      </div>

      <article aria-label="Final decision report" className="final-report">
        <header className="final-head">
          <div>
            <p className="rec-label">Underwriter decision record</p>
            <h2>{name}</h2>
            <p className="ws-muted">
              {[record.jurisdiction, record.industry].filter(Boolean).join(" · ") || "Jurisdiction not provided"}
            </p>
          </div>
          <TestPill />
        </header>

        <section className="final-decision">
          <span>Underwriter decision</span>
          <strong>{final}</strong>
          <p>
            {readable(decided.action)} by <b>{decided.decided_by}</b> on {dateTime(decided.decided_at)}.{" "}
            {decided.agrees ? "Matches the draft." : "Differs from the draft."}
          </p>
          {decided.reason && <p className="final-reason">Reason given: {decided.reason}</p>}
        </section>

        <dl className="final-grid">
          <div>
            <dt>Amount requested</dt>
            <dd>{money(draft.requested_amount, currency)}</dd>
          </div>
          <div>
            <dt>Draft recommendation (not a decision)</dt>
            <dd>
              {outcomeHeadline(draft)}
              {draft.outcome === "APPROVE" ? `: ${money(draft.recommended_amount, currency)}` : ""}
            </dd>
          </div>
          <div>
            <dt>Analyst proposed</dt>
            <dd>{draft.ai_proposed_amount ? money(draft.ai_proposed_amount, currency) : "No amount"}</dd>
          </div>
          <div>
            <dt>Draft version, policy</dt>
            <dd>
              v{draft.version}, policy v{draft.policy_version}
            </dd>
          </div>
        </dl>

        <section>
          <h3>Why the draft said this</h3>
          <p>{shorten(draft.summary, currency)}</p>
          <ol className="final-list">
            {draft.reasons.map((reason, index) => (
              <li key={`${index}-${reason.text}`}>
                {shorten(reason.text, currency)} <small>({reason.evidence.length} source{reason.evidence.length === 1 ? "" : "s"})</small>
              </li>
            ))}
          </ol>
        </section>

        {draft.factors.length > 0 && (
          <section>
            <h3>What lowered the amount</h3>
            <ul className="final-list">
              {draft.factors.map((factor) => (
                <li key={factor.code}>{shorten(factor.explanation, currency)}</li>
              ))}
            </ul>
          </section>
        )}

        <section>
          <h3>What is not known</h3>
          <ul className="final-list">
            {gaps.map((gap) => (
              <li key={gap}>{gap}</li>
            ))}
            {draft.limitations.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </section>

        <footer className="final-foot">
          <p>
            Prepared {dateTime(draft.created_at)} by {draft.created_by} with {draft.source.model} (method {draft.source.skill_version}).
            Test product: an internal evaluation record. It is not communicated to any customer and creates no commitment.
          </p>
        </footer>
      </article>
    </div>
  );
}
