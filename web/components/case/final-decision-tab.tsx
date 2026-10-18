"use client";

import { outcomeHeadline, TestPill } from "@/components/case/draft-hero";
import { loadDecision } from "@/components/case/decision-data";
import type { DraftRecord, TabProps } from "@/components/case/types";
import { useLoad } from "@/components/use-api";
import { api, type CaseRecord } from "@/lib/api/client";
import { dateTime, money, readable, shorten } from "@/lib/format";
import { splitGaps } from "@/lib/gaps";

type Props = TabProps & { record: CaseRecord };

/** One printable page: the underwriter's recorded decision, set beside the UW Analyzer recommendation it answers. */
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
            ? "Open the UW Analyzer recommendation tab and complete Step 3, Your decision. The one-page report appears here as soon as you record it."
            : "Ask the UW Analyzer for a recommendation on its tab first, then record your decision there."}
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
        : "No outcome recorded (recommendation set aside)";
  const gaps = splitGaps(draft.information_gaps).gaps;
  const analyzer =
    draft.outcome === "APPROVE" ? `${outcomeHeadline(draft)}: ${money(draft.recommended_amount, currency)}` : outcomeHeadline(draft);
  const sameOutcome = decided.final_outcome !== null && decided.final_outcome === draft.outcome;
  const verdict = decided.agrees
    ? "The actual decision matches the UW Analyzer recommendation."
    : decided.final_outcome === null
      ? "The UW Analyzer recommendation was set aside. No outcome was recorded."
      : sameOutcome
        ? `Same outcome, different amount: the UW Analyzer recommended ${money(draft.recommended_amount, currency)} and the actual decision is ${money(decided.final_amount, currency)}.`
        : "The actual decision differs from the UW Analyzer recommendation.";

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

        <section aria-label="UW Analyzer versus actual decision" className="final-compare">
          <h3>UW Analyzer versus actual decision</h3>
          <div className="final-compare-cols">
            <div>
              <span>UW Analyzer recommended</span>
              <strong>{analyzer}</strong>
              <small>Recommendation only. Version {draft.version}, policy v{draft.policy_version}.</small>
            </div>
            <div className="is-actual">
              <span>Actual decision</span>
              <strong>{final}</strong>
              <small>
                {readable(decided.action)} by <b>{decided.decided_by}</b> on {dateTime(decided.decided_at)}.
              </small>
            </div>
          </div>
          <p className="final-verdict">{verdict}</p>
          {decided.reason && <p className="final-reason">Reason given: {decided.reason}</p>}
        </section>

        <dl className="final-grid">
          <div>
            <dt>Amount requested</dt>
            <dd>{money(draft.requested_amount, currency)}</dd>
          </div>
          <div>
            <dt>UW Analyzer recommendation (not a decision)</dt>
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
            <dt>Recommendation version, policy</dt>
            <dd>
              v{draft.version}, policy v{draft.policy_version}
            </dd>
          </div>
        </dl>

        <section>
          <h3>Why the UW Analyzer said this</h3>
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
