"use client";

import { type FormEvent, useState } from "react";

import { type EscalationList, type EscalationRecord, type TabProps, can } from "@/components/case/types";
import { ActionError, useAction, useLoad } from "@/components/use-api";
import { api } from "@/lib/api/client";
import { dateTime, readable } from "@/lib/format";

function Resolve({
  base,
  item,
  onDone,
  token,
}: Readonly<{ base: string; item: EscalationRecord; onDone: () => void; token: string }>) {
  const action = useAction();
  const conflict = item.kind === "CONFLICT";
  const [outcome, setOutcome] = useState(conflict ? "SUPPORTING_PREVAILS" : "NO_CLAIM_CHANGE");
  const [evidenceId, setEvidenceId] = useState("");
  const [explanation, setExplanation] = useState("");
  const side = outcome === "SUPPORTING_PREVAILS" ? "SUPPORTS" : "CONTRADICTS";
  const options = (item.comparison ?? []).filter((row) => row.side === side);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const done = await action.run(() =>
      api(token, "POST", `${base}/${item.id}/resolution`, {
        outcome,
        explanation: explanation.trim(),
        preferred_evidence_id: conflict ? evidenceId || (options[0]?.evidence_id as string | undefined) : null,
      }),
    );
    if (done) onDone();
  }

  return (
    <form className="ws-form" onSubmit={submit}>
      <h4>Resolve in writing</h4>
      {conflict && (
        <>
          <label className="ws-field">
            Which side prevails?
            <select aria-label="Which side prevails?" onChange={(event) => setOutcome(event.target.value)} value={outcome}>
              <option value="SUPPORTING_PREVAILS">The supporting evidence prevails</option>
              <option value="CONTRADICTING_PREVAILS">The contradicting evidence prevails</option>
            </select>
          </label>
          <label className="ws-field">
            Evidence preferred
            <select aria-label="Evidence preferred" onChange={(event) => setEvidenceId(event.target.value)} value={evidenceId || String(options[0]?.evidence_id ?? "")}>
              {options.map((row) => (
                <option key={String(row.evidence_id)} value={String(row.evidence_id)}>
                  {String(row.title)} ({String(row.origin)})
                </option>
              ))}
            </select>
          </label>
        </>
      )}
      <label className="ws-field">
        Explanation (at least 10 characters: why this evidence or outcome was preferred)
        <textarea onChange={(event) => setExplanation(event.target.value)} required rows={3} value={explanation} />
      </label>
      <button className="ws-button primary" disabled={action.busy || explanation.trim().length < 10} type="submit">
        Record resolution
      </button>
      <ActionError error={action.error} />
    </form>
  );
}

export function ReviewTab({ caseId, onChanged, permissions, token }: TabProps) {
  const base = `/api/v1/cases/${encodeURIComponent(caseId)}/escalations`;
  const items = useLoad((t, signal) => api<EscalationList>(t, "GET", base, undefined, signal), [caseId]);
  const raise = useAction();
  const canRaise = can(permissions, "research:run");
  const canResolve = can(permissions, "conflict:resolve");
  const list = items.data?.items ?? [];

  async function raiseItem(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const done = await raise.run(() =>
      api(token, "POST", base, { kind: String(data.get("kind")), description: String(data.get("description")).trim() }),
    );
    if (done) {
      form.reset();
      items.reload();
      onChanged();
    }
  }

  return (
    <div className="ws-stack">
      <section className="ws-card">
        <h2>Review items</h2>
        <p>
          Items that need a person. When reliable sources disagree about a material claim, the system raises a review item
          automatically. Only a reviewer can close it, in writing; nothing closes it automatically. A report cannot be
          completed while any item is open.
        </p>
        <p className="ws-pill-row">
          <span className="ws-pill">Open items: {items.data?.open_count ?? 0}</span>
          {!canResolve && <span className="ws-pill">Your role cannot resolve items</span>}
        </p>
      </section>

      {list.length === 0 && (
        <section className="ws-card">
          <p>Nothing has been raised for this case.</p>
        </section>
      )}

      {list.map((item) => (
        <section className="ws-card" key={item.id}>
          <p className="ws-pill-row">
            <span className="ws-pill">{item.label.replaceAll("_", " ")}</span>
            <span className="ws-pill">{readable(item.kind)}</span>
            <span className="ws-pill">{readable(item.state)}</span>
          </p>
          <p className="ws-claim-text">{item.description}</p>
          <p className="ws-muted">
            Raised {dateTime(item.created_at)} by {item.raised_by_system ? "the system" : item.created_by}
          </p>
          {(item.comparison ?? []).length > 0 && (
            <div className="ws-table-wrap">
              <table className="ws-table">
                <thead>
                  <tr>
                    <th>Side</th>
                    <th>Source</th>
                    <th>Authority</th>
                    <th>Date</th>
                    <th>Specificity</th>
                    <th>Independent</th>
                    <th>Data quality</th>
                  </tr>
                </thead>
                <tbody>
                  {(item.comparison ?? []).map((row) => (
                    <tr key={String(row.evidence_id)}>
                      <td>{readable(String(row.side))}</td>
                      <td>
                        {String(row.title)}
                        <small className="ws-muted"> {String(row.origin)}</small>
                      </td>
                      <td>{readable(String(row.authority))}</td>
                      <td>
                        {String(row.date)} ({readable(String(row.freshness)).toLowerCase()})
                      </td>
                      <td>{String(row.specificity)}</td>
                      <td>{row.independent_of_other_side ? "Yes" : "No"}</td>
                      <td>{String(row.data_quality)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {item.resolution && (
            <p className="ws-note">
              Resolved by {item.resolution.resolved_by} on {dateTime(item.resolution.resolved_at)}:{" "}
              {readable(item.resolution.outcome)}. {item.resolution.explanation}
            </p>
          )}
          {item.state === "OPEN" && canResolve && (
            <Resolve
              base={base}
              item={item}
              onDone={() => {
                items.reload();
                onChanged();
              }}
              token={token}
            />
          )}
        </section>
      ))}

      {canRaise && (
        <section className="ws-card">
          <h3>Raise an item for review</h3>
          <form className="ws-form" onSubmit={raiseItem}>
            <label className="ws-field">
              Kind
              <select aria-label="Kind" name="kind">
                <option value="MATERIAL_AMBIGUITY">Material ambiguity</option>
                <option value="OTHER">Other</option>
              </select>
            </label>
            <label className="ws-field">
              What needs a person&apos;s attention
              <textarea name="description" required rows={3} />
            </label>
            <button className="ws-button" disabled={raise.busy} type="submit">
              Raise for review
            </button>
            <ActionError error={raise.error} />
          </form>
        </section>
      )}
    </div>
  );
}
