"use client";

import { useState } from "react";

import type { components } from "@/lib/api/schema";
import { ActionError, useAction } from "@/components/use-api";
import { api } from "@/lib/api/client";

export type AnalysisResult = components["schemas"]["AnalysisOut"];

function ResultView({ result }: Readonly<{ result: AnalysisResult }>) {
  return (
    <div className="ws-stack">
      <p className="ws-note">{result.message}</p>
      <p className="ws-muted">
        {result.evidence_created} evidence item(s) and {result.claims_created} finding(s) were added; see Evidence and claims.
        The full analysis is shown below.
      </p>
    </div>
  );
}

export function AnalysisPanel({
  base,
  canRun,
  hasDraft = false,
  onDone,
  token,
}: Readonly<{ base: string; canRun: boolean; hasDraft?: boolean; onDone: () => void; token: string }>) {
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
      <h3>{hasDraft ? "Analyse again for a new recommendation version" : "Prepare the UW Analyzer recommendation from the research"}</h3>
      <p>
        The analyzer reads the finished research (the exact copies fetched from the public sources), assesses the five
        dimensions (liquidity, profitability, leverage, cash flow, efficiency and sector) and the other research areas, and prepares the UW Analyzer recommendation for you. It records every finding
        it relies on. It does not decide anything; you decide below.
      </p>
      {canRun ? (
        <button className="ws-button primary" disabled={action.busy} onClick={run} type="button">
          {action.busy ? "Analysing…" : hasDraft ? "Analyse the research again and prepare a new recommendation" : "Analyse the research and prepare the recommendation"}
        </button>
      ) : (
        <p className="ws-muted">Your role cannot run the analysis.</p>
      )}
      <ActionError error={action.error} />
      {result && <ResultView result={result} />}
    </section>
  );
}
