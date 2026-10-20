"use client";

import { useSession } from "@/components/session-provider";
import { Gate, useLoad } from "@/components/use-api";
import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { dateTime } from "@/lib/format";

type AuditEvent = components["schemas"]["AuditEventOut"];

export function AuditTrail() {
  const { session } = useSession();
  const events = useLoad(
    (token, signal) => api<AuditEvent[]>(token, "GET", "/api/v1/audit-events?limit=100", undefined, signal),
    [],
  );

  return (
    <Gate error={events.error} loading={events.loading} name="Audit history" signedIn={Boolean(session)}>
      <section className="ws">
        <header className="ws-header">
          <div>
            <p className="eyebrow">Governance</p>
            <h1>Audit history</h1>
            <p className="ws-muted">
              Every material action, newest first. The log can only be added to, and case content is never copied into it.
              Only the auditor role can read it.
            </p>
          </div>
        </header>
        <section className="ws-card">
          <div className="ws-table-wrap">
            <table className="ws-table">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Who</th>
                  <th>Action</th>
                  <th>Outcome</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {(events.data ?? []).map((event) => (
                  <tr key={event.id}>
                    <td>{dateTime(event.occurred_at)}</td>
                    <td>{event.actor ?? "system"}</td>
                    <td>{event.action}</td>
                    <td>{event.outcome}</td>
                    <td>
                      <small className="ws-muted">
                        {Object.entries(event.details)
                          .map(([key, value]) => `${key}: ${value}`)
                          .join(" · ")}
                      </small>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {(events.data ?? []).length === 0 && <p>No events yet.</p>}
        </section>
      </section>
    </Gate>
  );
}
