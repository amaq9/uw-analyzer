"use client";

import { useState } from "react";

import type { components } from "@/lib/api/schema";
import { ActionError, useAction } from "@/components/use-api";
import { api } from "@/lib/api/client";
import { money, readable } from "@/lib/format";

export type AnalysisResult = components["schemas"]["AnalysisOut"];

function ResultView({ result }: Readonly<{ result: AnalysisResult }>) {
  const currency = result.currency;
  return (
    <div className="ws-stack">
      <p className="ws-note">{result.message}</p>
      <div className="ws-table-wrap">
        <table className="ws-table">
          <thead>
            <tr>
              <th>Section</th>
              <th>Assessment</th>
              <th>Direction</th>
              <th>Why</th>
            </tr>
          </thead>
          <tbody>
            {result.sections.map((section) => (
              <tr key={section.key}>
                <td>{section.title}</td>
                <td>
                  <strong>{readable(section.assessment)}</strong>
                </td>
                <td>{section.trend}</td>
                <td>
                  {section.why}
                  {section.flags.length > 0 && <small className="ws-muted">Flags: {section.flags.join("; ")}</small>}
                </td>
              </tr>
            ))}
            {result.consolidated_assessment && (
              <tr>
                <td>
                  <strong>Consolidated financial findings</strong>
                </td>
                <td>
                  <strong>{readable(result.consolidated_assessment)}</strong>
                </td>
                <td />
                <td>{result.consolidated_why}</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="ws-muted">
        These are descriptions of the evidence in words. They are not scores or ratings. Periods reviewed:{" "}
        {result.periods_reviewed.join(", ") || "none"}.
      </p>
      {result.proposed_amount && (
        <p>
          The analyst proposes <strong>{money(result.proposed_amount, currency)}</strong> of{" "}
          {money(result.requested_amount, currency)} requested. The approved policy then sets the draft outcome.
        </p>
      )}
      {result.factors.length > 0 && (
        <ul className="ws-bullets">
          {result.factors.map((factor) => (
            <li key={factor.code}>{factor.explanation}</li>
          ))}
        </ul>
      )}
      {result.information_gaps.length > 0 && (
        <details>
          <summary>Information gaps and limits ({result.information_gaps.length})</summary>
          <ul className="ws-bullets">
            {result.information_gaps.map((gap) => (
              <li key={gap}>{gap}</li>
            ))}
          </ul>
        </details>
      )}
      <p className="ws-muted">
        {result.evidence_created} evidence item(s) and {result.claims_created} finding(s) were added; see Evidence and claims.
      </p>
    </div>
  );
}

export function AnalysisPanel({
  base,
  canRun,
  onDone,
  token,
}: Readonly<{ base: string; canRun: boolean; onDone: () => void; token: string }>) {
  const action = useAction();
  const [result, setResult] = useState<AnalysisResult>();

  async function run() {
    const done = await action.run(() => api<AnalysisResult>(token, "POST", `${base}/analysis`, {}));
    if (done) {
      setResult(done);
      onDone();
    }
  }

  return (
    <section className="ws-card">
      <h3>Prepare a draft recommendation from the research</h3>
      <p>
        The analyzer reads the finished research (the exact copies fetched from the public sources), assesses the five
        financial areas and the other research areas, and prepares a draft recommendation for you. It records every finding
        it relies on. It does not decide anything; you decide below.
      </p>
      {canRun ? (
        <button className="ws-button primary" disabled={action.busy} onClick={run} type="button">
          {action.busy ? "Analysing…" : "Analyse the research and prepare a draft"}
        </button>
      ) : (
        <p className="ws-muted">Your role cannot run the analysis.</p>
      )}
      <ActionError error={action.error} />
      {result && <ResultView result={result} />}
    </section>
  );
}
