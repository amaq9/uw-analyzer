"use client";

import Link from "next/link";

import { outcomeHeadline, TestPill } from "@/components/case/draft-hero";
import type { DecisionRecord, DraftRecord } from "@/components/case/types";
import { useSession } from "@/components/session-provider";
import { Gate, useLoad } from "@/components/use-api";
import { ApiRequestError, api, listCases, type CaseRecord } from "@/lib/api/client";
import { dateTime, money } from "@/lib/format";

type Row = { record: CaseRecord; draft?: DraftRecord; decision?: DecisionRecord | null };

async function loadRows(token: string, signal: AbortSignal): Promise<Row[]> {
  const cases = await listCases(token, 50, 0, signal);
  return Promise.all(
    cases.map(async (record) => {
      const base = `/api/v1/cases/${record.id}/draft-recommendations`;
      const drafts = await api<DraftRecord[]>(token, "GET", base, undefined, signal);
      const draft = drafts[0];
      if (!draft) return { record };
      try {
        const decision = await api<DecisionRecord>(token, "GET", `${base}/${draft.id}/decision`, undefined, signal);
        return { record, draft, decision };
      } catch (error) {
        if (error instanceof ApiRequestError && error.status === 404) return { record, draft, decision: null };
        throw error;
      }
    }),
  );
}

function status(row: Row) {
  if (!row.draft) return "No recommendation yet";
  return row.decision ? "Decided by you" : "Waiting for your decision";
}

export function RecommendationsOverview() {
  const { session } = useSession();
  const rows = useLoad(loadRows, []);
  const data = rows.data ?? [];
  const waiting = data.filter((row) => row.draft && !row.decision).length;

  return (
    <Gate error={rows.error} loading={rows.loading} name="UW Analyzer recommendations" signedIn={Boolean(session)}>
      <section className="ws">
        <header className="ws-header">
          <div>
            <p className="eyebrow">Step 2 and 3 · UW Analyzer and decision</p>
            <h1>UW Analyzer recommendations</h1>
            <p className="ws-muted">
              Every draft is a recommendation for the underwriter, not a decision. Only your recorded decision is.
            </p>
          </div>
          <TestPill />
        </header>

        <section className="ws-card">
          <p>
            {waiting > 0
              ? `${waiting} recommendation${waiting === 1 ? " is" : "s are"} waiting for your decision.`
              : "No recommendation is waiting for your decision."}
          </p>
          {data.length === 0 ? (
            <p className="ws-muted">
              There are no cases yet. <Link className="ws-link" href="/cases/new">Create a case</Link> to start.
            </p>
          ) : (
            <div className="ws-table-wrap">
              <table className="ws-table">
                <thead>
                  <tr>
                    <th>Case</th>
                    <th>Requested</th>
                    <th>UW Analyzer said</th>
                    <th>Where it stands</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {data.map((row) => (
                    <tr key={row.record.id}>
                      <td>
                        <strong>{row.record.legal_name ?? row.record.trading_name ?? "Unnamed case"}</strong>
                        <small className="ws-muted">{dateTime(row.record.updated_at)}</small>
                      </td>
                      <td>{money(row.record.exposure_amount, row.record.exposure_currency)}</td>
                      <td>
                        {row.draft ? (
                          <>
                            {outcomeHeadline(row.draft)}
                            {row.draft.outcome === "APPROVE"
                              ? `: ${money(row.draft.recommended_amount, row.draft.requested_currency)}`
                              : ""}
                          </>
                        ) : (
                          "Not prepared"
                        )}
                      </td>
                      <td>{status(row)}</td>
                      <td>
                        <Link className="ws-link" href={`/cases/${row.record.id}?tab=recommendation`}>
                          {row.draft ? "Open the recommendation" : "Open the case"}
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </section>
    </Gate>
  );
}
