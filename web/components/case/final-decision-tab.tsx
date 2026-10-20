"use client";

import { DecisionSummary } from "@/components/case/decision-summary";
import { loadDecision } from "@/components/case/decision-data";
import type { DraftRecord, TabProps } from "@/components/case/types";
import { useLoad } from "@/components/use-api";
import { api, type CaseRecord } from "@/lib/api/client";

type Props = TabProps & { record: CaseRecord };

/** The UW Analyzer Decision Summary: the underwriter's recorded decision on one printable page. */
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
            ? "Open the UW Analyzer recommendation tab and complete Step 3, Your decision. The one-page summary appears here as soon as you record it."
            : "Ask the UW Analyzer for a recommendation on its tab first, then record your decision there."}
        </p>
      </section>
    );
  }

  return (
    <div className="ws-stack">
      <div className="final-actions no-print">
        <p className="ws-muted">One page. Use the button, then choose “Save as PDF” as the printer to keep a copy.</p>
        <button className="ws-button primary" onClick={() => window.print()} type="button">
          Print or save as PDF
        </button>
      </div>
      <DecisionSummary decided={decided} draft={draft} record={record} />
    </div>
  );
}
