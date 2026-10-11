"use client";

import { type FormEvent, useEffect, useState } from "react";

import { type CallRecord, type RunRecord, type TabProps, can } from "@/components/case/types";
import { ActionError, useAction, useLoad } from "@/components/use-api";
import { api, fetchBlob } from "@/lib/api/client";
import { dateTime, readable } from "@/lib/format";

const IN_FLIGHT = new Set(["QUEUED", "RUNNING"]);
const SNAPSHOT_LIMIT = 20000;

export function SnapshotViewer({ caseId, reference, token }: Readonly<{ caseId: string; reference: string; token: string }>) {
  const [text, setText] = useState<string>();
  const action = useAction();

  async function show() {
    const blob = await action.run(() =>
      fetchBlob(token, `/api/v1/cases/${encodeURIComponent(caseId)}/snapshots?ref=${encodeURIComponent(reference)}`),
    );
    if (blob) setText(await blob.text());
  }

  if (text !== undefined) {
    return (
      <details open>
        <summary>Source material (exact copy, hash checked)</summary>
        <pre className="ws-pre">
          {text.length > SNAPSHOT_LIMIT ? `${text.slice(0, SNAPSHOT_LIMIT)}\n… (shortened for display)` : text}
        </pre>
      </details>
    );
  }
  return (
    <>
      <button className="ws-button" disabled={action.busy} onClick={show} type="button">
        Show source material
      </button>
      <ActionError error={action.error} />
    </>
  );
}

export function ResearchTab({ caseId, onChanged, permissions, token }: TabProps) {
  const base = `/api/v1/cases/${encodeURIComponent(caseId)}`;
  const runs = useLoad((t, signal) => api<RunRecord[]>(t, "GET", `${base}/research-runs`, undefined, signal), [caseId]);
  const [selectedId, setSelectedId] = useState<string>();
  const list = runs.data ?? [];
  const selected = list.find((run) => run.id === selectedId) ?? list[0];
  const calls = useLoad(
    (t, signal) =>
      selected
        ? api<CallRecord[]>(t, "GET", `${base}/research-runs/${selected.id}/connector-calls`, undefined, signal)
        : Promise.resolve([] as CallRecord[]),
    [caseId, selected?.id, selected?.status],
  );
  const plan = useAction();
  const start = useAction();
  const canRun = can(permissions, "research:run");
  const reloadRuns = runs.reload;
  const inFlight = selected ? IN_FLIGHT.has(selected.status) : false;

  useEffect(() => {
    if (!inFlight) return;
    const timer = setInterval(reloadRuns, 4000);
    return () => clearInterval(timer);
  }, [inFlight, reloadRuns]);

  async function createPlan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const raw = String(new FormData(form).get("countries") ?? "");
    const jurisdictions = raw
      .split(/[\s,]+/)
      .map((code) => code.trim().toUpperCase())
      .filter(Boolean);
    const created = await plan.run(() => api<RunRecord>(token, "POST", `${base}/research-runs`, { jurisdictions }));
    if (created) {
      form.reset();
      setSelectedId(created.id);
      runs.reload();
      onChanged();
    }
  }

  async function startRun(run: RunRecord) {
    const started = await start.run(() => api<RunRecord>(token, "POST", `${base}/research-runs/${run.id}/start`));
    if (started) {
      runs.reload();
      onChanged();
    }
  }

  return (
    <div className="ws-stack">
      <section className="ws-card">
        <h2>Research</h2>
        <p>
          Research fetches public sources through logged connector calls. <strong>Accessed</strong> means a call
          succeeded and returned material. It does <strong>not</strong> mean anything is verified; that is decided later
          from the evidence. Sources that could not be used are listed with the reason, never hidden.
        </p>
      </section>

      {canRun && (
        <section className="ws-card">
          <h3>Plan new research</h3>
          <form className="ws-form" onSubmit={createPlan}>
            <label className="ws-field">
              Countries to cover (two-letter codes, separated by commas: the company&apos;s country, its parent&apos;s, where it
              operates)
              <input defaultValue="US" name="countries" required />
            </label>
            <button className="ws-button primary" disabled={plan.busy} type="submit">
              Create research plan
            </button>
            <ActionError error={plan.error} />
          </form>
          <p className="ws-muted">Research is blocked until the legal entity has been chosen on the Entity tab.</p>
        </section>
      )}

      {list.length > 1 && (
        <section className="ws-card">
          <h3>Earlier plans and runs</h3>
          <ul className="ws-list">
            {list.map((run) => (
              <li key={run.id}>
                <button className="ws-link" onClick={() => setSelectedId(run.id)} type="button">
                  {dateTime(run.created_at)} · {run.jurisdictions.join(", ")} · {readable(run.status)}
                  {run.id === selected?.id ? " (shown)" : ""}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {selected ? (
        <section className="ws-card">
          <div className="ws-row">
            <div>
              <h3>
                Run for {selected.jurisdictions.join(", ")}: {readable(selected.status)}
              </h3>
              <p className="ws-muted">
                Planned {dateTime(selected.created_at)} by {selected.created_by}
                {selected.started_at ? ` · started ${dateTime(selected.started_at)}` : ""}
                {selected.completed_at ? ` · finished ${dateTime(selected.completed_at)}` : ""}
              </p>
            </div>
            {canRun && (selected.status === "PLANNED" || selected.status === "FAILED") && (
              <button className="ws-button primary" disabled={start.busy} onClick={() => startRun(selected)} type="button">
                {selected.status === "FAILED" ? "Try the failed steps again" : "Start research"}
              </button>
            )}
          </div>
          <ActionError error={start.error} />
          {inFlight && <p className="ws-note">Research is running. This page refreshes itself. The worker window must be open.</p>}
          <div className="ws-table-wrap">
            <table className="ws-table">
              <thead>
                <tr>
                  <th>Area</th>
                  <th>Source</th>
                  <th>State</th>
                  <th>Accessed</th>
                  <th>Attempts</th>
                  <th>Note</th>
                </tr>
              </thead>
              <tbody>
                {selected.steps.map((step) => (
                  <tr key={step.id}>
                    <td>{readable(step.category)}</td>
                    <td>
                      {String((step.source as Record<string, unknown>).name ?? "No source registered")}
                    </td>
                    <td>{readable(step.state)}</td>
                    <td>{step.accessed ? "Yes" : "No"}</td>
                    <td>
                      {step.attempts}/{step.max_attempts}
                    </td>
                    <td>{[step.reason, step.error_class && `Error: ${step.error_class}`].filter(Boolean).join(" · ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="ws-muted">
            Versions recorded: app {String(selected.versions.app)}, plan rules {String(selected.versions.plan_rules)}, policy{" "}
            {String(selected.versions.policy)}.
          </p>
        </section>
      ) : (
        <section className="ws-card">
          <p>No research has been planned yet.</p>
        </section>
      )}

      {selected && (
        <section className="ws-card">
          <h3>Connector call log</h3>
          {(calls.data ?? []).length === 0 ? (
            <p>No connector call has been made for this run.</p>
          ) : (
            <ul className="ws-list">
              {(calls.data ?? []).map((call) => (
                <li key={call.id}>
                  <strong>{call.source_key}</strong> · attempt {call.attempt} · {readable(call.outcome)}
                  {call.error_class ? ` (${call.error_class})` : ""}
                  <p className="ws-muted">
                    {call.action}. {dateTime(call.started_at)} to {dateTime(call.ended_at)}. Source status at the time:{" "}
                    {readable(call.access_status)}.
                  </p>
                  {call.provenance_ref && <SnapshotViewer caseId={caseId} reference={call.provenance_ref} token={token} />}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
