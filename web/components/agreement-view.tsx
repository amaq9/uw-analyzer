"use client";

import Link from "next/link";

import type { AgreementReport } from "@/components/case/types";
import { useSession } from "@/components/session-provider";
import { Gate, useLoad } from "@/components/use-api";
import { api } from "@/lib/api/client";
import { dateTime, money, readable } from "@/lib/format";

export function AgreementView() {
  const { session } = useSession();
  const report = useLoad((token, signal) => api<AgreementReport>(token, "GET", "/api/v1/agreement?limit=200", undefined, signal), []);
  const data = report.data;

  return (
    <Gate error={report.error} loading={report.loading} name="Decision Outcome" signedIn={Boolean(session)}>
      {data && (
        <section className="ws">
          <header className="ws-header">
            <div>
              <p className="eyebrow">UW Analyzer versus actual decision</p>
              <h1>Decision Outcome</h1>
              <p className="ws-muted">{data.notice}</p>
            </div>
          </header>

          <section className="ws-card">
            <h3>Totals</h3>
            <dl className="ws-facts">
              <div>
                <dt>Recommendations decided on</dt>
                <dd>{data.totals.decided}</dd>
              </div>
              <div>
                <dt>Adopted as written</dt>
                <dd>{data.totals.adopted}</dd>
              </div>
              <div>
                <dt>Changed</dt>
                <dd>{data.totals.changed}</dd>
              </div>
              <div>
                <dt>Set aside</dt>
                <dd>{data.totals.rejected}</dd>
              </div>
              <div>
                <dt>Same outcome</dt>
                <dd>{data.totals.same_outcome}</dd>
              </div>
              <div>
                <dt>Different outcome</dt>
                <dd>{data.totals.different_outcome}</dd>
              </div>
              <div>
                <dt>Same outcome, different amount</dt>
                <dd>{data.totals.amount_differs_same_outcome}</dd>
              </div>
            </dl>
          </section>

          <section className="ws-card">
            <h3>Each decided recommendation</h3>
            {data.rows.length === 0 ? (
              <p>No decision has been recorded yet. Record one on a case&apos;s UW Analyzer recommendation tab.</p>
            ) : (
              <div className="ws-table-wrap">
                <table className="ws-table">
                  <thead>
                    <tr>
                      <th>Case</th>
                      <th>UW Analyzer said</th>
                      <th>Actual decision</th>
                      <th>Match</th>
                      <th>Reason given</th>
                      <th>When</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.rows.map((row) => (
                      <tr key={row.draft_id}>
                        <td>
                          <Link className="ws-link" href={`/cases/${row.case_id}`}>
                            Open case
                          </Link>
                          <small className="ws-muted"> recommendation v{row.draft_version}</small>
                        </td>
                        <td>
                          {readable(row.draft_outcome)}
                          {row.draft_amount ? ` ${money(row.draft_amount, row.currency)}` : ""}
                          <small className="ws-muted"> analyst proposed {money(row.ai_proposed_amount, row.currency)}</small>
                        </td>
                        <td>
                          {row.final_outcome ? readable(row.final_outcome) : "Set aside"}
                          {row.final_amount ? ` ${money(row.final_amount, row.currency)}` : ""}
                          <small className="ws-muted"> {readable(row.action)}</small>
                        </td>
                        <td>{row.agrees ? "Agrees" : row.same_outcome ? "Same outcome, changed" : "Differs"}</td>
                        <td>{row.reason ?? ""}</td>
                        <td>{dateTime(row.decided_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </section>
      )}
    </Gate>
  );
}
