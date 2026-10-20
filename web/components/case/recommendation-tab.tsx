"use client";

import Link from "next/link";

import { AnalysisPanel } from "@/components/case/analysis-panel";
import { AnalysisReportView } from "@/components/case/analysis-report";
import { PublishedRatings } from "@/components/case/published-ratings";
import { DecisionForm, DecisionSummary } from "@/components/case/decision-form";
import { loadDecision } from "@/components/case/decision-data";
import { ExecutiveBriefCard } from "@/components/case/executive-brief";
import { AnalysisFindings, DraftBasis, DraftHero, outcomeHeadline, StepHeading } from "@/components/case/draft-hero";
import { type DraftRecord, type TabProps, can } from "@/components/case/types";
import { useLoad } from "@/components/use-api";
import { api } from "@/lib/api/client";
import { dateTime, money } from "@/lib/format";

const RECENT_EARLIER = 3; // earlier versions shown before "show older"

function EarlierList({ caseId, drafts }: Readonly<{ caseId: string; drafts: DraftRecord[] }>) {
  return (
    <ul className="ws-list">
      {drafts.map((draft) => (
        <li key={draft.id}>
          <Link className="ws-link" href={`/cases/${caseId}/recommendations/${draft.id}`}>
            Version {draft.version} · {dateTime(draft.created_at)}
          </Link>
          <small className="ws-muted">
            UW Analyzer said: {outcomeHeadline(draft)}
            {draft.outcome === "APPROVE" ? ` (${money(draft.recommended_amount, draft.requested_currency)})` : ""}
          </small>
        </li>
      ))}
    </ul>
  );
}

function Steps({ hasDraft, decided }: Readonly<{ hasDraft: boolean; decided: boolean }>) {
  const steps = [
    { id: "rec-step-1", label: "Research and analysis", state: hasDraft ? "done" : "current" },
    { id: "rec-step-2", label: "UW Analyzer recommendation", state: !hasDraft ? "next" : decided ? "done" : "current" },
    { id: "rec-step-3", label: "Your decision", state: decided ? "done" : hasDraft ? "current" : "next" },
  ];
  return (
    <ol aria-label="Progress" className="rec-steps">
      {steps.map((step, index) => (
        <li aria-current={step.state === "current" ? "step" : undefined} className={`is-${step.state}`} key={step.label}>
          <a href={`#${step.id}`}>
            <span className="rec-step-dot">{step.state === "done" ? "✓" : index + 1}</span>
            <span>{step.label}</span>
          </a>
        </li>
      ))}
    </ol>
  );
}

export function RecommendationTab({
  caseId,
  onChanged,
  onOpenTab,
  permissions,
  token,
}: TabProps & { onOpenTab?: (tab: "final") => void }) {
  const base = `/api/v1/cases/${encodeURIComponent(caseId)}/draft-recommendations`;
  const drafts = useLoad((t, signal) => api<DraftRecord[]>(t, "GET", base, undefined, signal), [caseId]);
  const list = drafts.data ?? [];
  const latest = list[0];
  const decision = useLoad(
    (t, signal) => (latest ? loadDecision(t, base, latest.id, signal) : Promise.resolve(null)),
    [caseId, latest?.id],
  );
  const canDecide = can(permissions, "decision:record");
  const decided = Boolean(decision.data);

  return (
    <div className="ws-stack rec">
      <Steps decided={decided} hasDraft={Boolean(latest)} />

      <StepHeading
        id="rec-step-1"
        note="The analyzer reads the finished research and the uploaded statements, and records what it found with its sources."
        number={1}
        title="Research and analysis"
      />
      <AnalysisPanel
        base={`/api/v1/cases/${encodeURIComponent(caseId)}`}
        canRun={can(permissions, "draft:import")}
        hasDraft={Boolean(latest)}
        onDone={() => {
          drafts.reload();
          decision.reload();
          onChanged();
        }}
        token={token}
      />
      {latest?.analysis && <AnalysisReportView currency={latest.requested_currency} report={latest.analysis} />}
      {latest && !latest.analysis && (
        <p className="ws-note">
          This recommendation was prepared before the detailed analysis existed. Run the analysis again to see the full Step 1 here.
        </p>
      )}
      <PublishedRatings
        analysis={latest?.analysis}
        canRecord={can(permissions, "draft:import")}
        caseId={caseId}
        token={token}
      />
      {latest && <AnalysisFindings draft={latest} />}

      {drafts.error && (
        <p className="ws-error" role="alert">
          The recommendations could not be loaded. {drafts.error.message}
        </p>
      )}

      <StepHeading
        id="rec-step-2"
        note="The approved policy turns the findings into the UW Analyzer's outcome and amount. It is a recommendation only."
        number={2}
        title="UW Analyzer recommendation"
      />
      {drafts.loading && !drafts.data && (
        <section aria-live="polite" className="ws-card">
          <p className="ws-muted">Loading the recommendations of this case…</p>
        </section>
      )}
      {!latest && !drafts.loading && !drafts.error && (
        <section className="ws-card rec-empty">
          <h3>No UW Analyzer recommendation has been prepared yet</h3>
          <p>
            Run the analysis in Step 1 once the research has finished. A recommendation needs a confirmed company, no open review
            items, and finished research and financial analysis. If any is missing, the analysis says which.
          </p>
        </section>
      )}
      {latest && <DraftHero draft={latest} />}
      {latest?.analysis?.executive_brief && (
        <ExecutiveBriefCard brief={latest.analysis.executive_brief} currency={latest.requested_currency} />
      )}
      {latest && <DraftBasis draft={latest} />}

      <StepHeading
        id="rec-step-3"
        note="Only your recorded decision is the decision. Adopt the UW Analyzer recommendation, change it, or reject it."
        number={3}
        title="Your decision"
      />
      {!latest && !drafts.loading && !drafts.error && (
        <section className="ws-card">
          <p>Available once the UW Analyzer has prepared a recommendation.</p>
        </section>
      )}
      {latest && decision.data && <DecisionSummary decision={decision.data} draft={latest} />}
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
      {latest && decision.data && (
        <section className="ws-card rec-report-prompt">
          <div>
            <p className="eyebrow">Next</p>
            <h3>Your UW Analyzer Decision Summary is ready</h3>
            <p className="ws-muted">Open the Final decision tab to print it or save it as a PDF.</p>
          </div>
          <button className="ws-button primary" onClick={() => onOpenTab?.("final")} type="button">
            Open the Final decision tab
          </button>
        </section>
      )}

      {list.length > 1 && (
        <section className="ws-card">
          <p className="eyebrow">Earlier recommendations of this case</p>
          <EarlierList caseId={caseId} drafts={list.slice(1, 1 + RECENT_EARLIER)} />
          {list.length > 1 + RECENT_EARLIER && (
            <details className="ws-details">
              <summary>Show {list.length - 1 - RECENT_EARLIER} older versions</summary>
              <EarlierList caseId={caseId} drafts={list.slice(1 + RECENT_EARLIER)} />
            </details>
          )}
        </section>
      )}
    </div>
  );
}
