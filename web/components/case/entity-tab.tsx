"use client";

import { type FormEvent, useState } from "react";

import { type Candidate, type Readiness, type TabProps, can } from "@/components/case/types";
import { ActionError, useAction, useLoad } from "@/components/use-api";
import { api } from "@/lib/api/client";
import { readable } from "@/lib/format";

type EntityTabProps = TabProps & { status: string };

export function EntityTab({ caseId, onChanged, permissions, status, token }: EntityTabProps) {
  const base = `/api/v1/cases/${encodeURIComponent(caseId)}`;
  const candidates = useLoad((t, signal) => api<Candidate[]>(t, "GET", `${base}/entity-candidates`, undefined, signal), [caseId, status]);
  const readiness = useLoad((t, signal) => api<Readiness>(t, "GET", `${base}/research-readiness`, undefined, signal), [caseId, status]);
  const add = useAction();
  const resolve = useAction();
  const reopen = useAction();
  const unconfirmed = useAction();
  const [note, setNote] = useState("");
  const [reason, setReason] = useState("");
  const canWrite = can(permissions, "case:write");
  const resolved = status === "ENTITY_RESOLVED";
  const closed = resolved || status === "ENTITY_UNCONFIRMED";

  function refresh() {
    candidates.reload();
    readiness.reload();
    onChanged();
  }

  async function addCandidate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const text = (key: string) => String(data.get(key) ?? "").trim() || null;
    const done = await add.run(() =>
      api(token, "POST", `${base}/entity-candidates`, {
        legal_name: String(data.get("legal_name") ?? "").trim(),
        registration_number: text("registration_number"),
        jurisdiction: text("jurisdiction"),
        website: text("website"),
        address: text("address"),
      }),
    );
    if (done) {
      form.reset();
      refresh();
    }
  }

  async function choose(candidateId: string) {
    const done = await resolve.run(() =>
      api(token, "POST", `${base}/entity-resolution`, { candidate_id: candidateId, note: note.trim() || null }),
    );
    if (done) {
      setNote("");
      refresh();
    }
  }

  async function reopenResolution() {
    const done = await reopen.run(() => api(token, "POST", `${base}/entity-resolution/reopen`, { reason: reason.trim() }));
    if (done) {
      setReason("");
      refresh();
    }
  }

  async function markUnconfirmed() {
    const done = await unconfirmed.run(() =>
      api(token, "POST", `${base}/entity-resolution/unconfirmed`, { reason: reason.trim() }),
    );
    if (done) {
      setReason("");
      refresh();
    }
  }

  const list = candidates.data ?? [];
  const blockers = readiness.data?.blockers ?? [];

  return (
    <div className="ws-stack">
      <section className="ws-card">
        <h2>Which legal entity is this?</h2>
        <p>
          Research only starts once one exact legal entity is chosen by a person. If more than one could match, research
          stays stopped until you choose.
        </p>
        <p className="ws-pill-row">
          <span className="ws-pill">Case status: {readable(status)}</span>
          <span className="ws-pill">{readiness.data?.allowed ? "Research may start" : "Research is blocked"}</span>
        </p>
        {blockers.map((blocker) => (
          <p className="ws-note" key={blocker.code}>
            {blocker.message}
          </p>
        ))}
      </section>

      <section className="ws-card">
        <h3>Candidate legal entities</h3>
        {list.length === 0 && <p>No candidate has been added yet.</p>}
        <ul className="ws-list">
          {list.map((candidate) => (
            <li key={candidate.id}>
              <div className="ws-row">
                <div>
                  <strong>{candidate.legal_name}</strong>
                  <span className="ws-pill">{readable(candidate.state)}</span>
                  <p className="ws-muted">
                    {[candidate.registration_number, candidate.jurisdiction, candidate.website, candidate.address]
                      .filter(Boolean)
                      .join(" · ") || "No further details"}
                  </p>
                </div>
                {canWrite && candidate.state === "candidate" && !closed && (
                  <button className="ws-button" disabled={resolve.busy} onClick={() => choose(candidate.id)} type="button">
                    Choose this entity
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
        {canWrite && !closed && (
          <label className="ws-field">
            Note for the record (optional)
            <input onChange={(event) => setNote(event.target.value)} value={note} />
          </label>
        )}
        <ActionError error={resolve.error} />
      </section>

      {canWrite && !closed && (
        <section className="ws-card">
          <h3>Add a candidate entity</h3>
          <form className="ws-form" onSubmit={addCandidate}>
            <label className="ws-field">
              Exact legal name
              <input name="legal_name" required />
            </label>
            <label className="ws-field">
              Registration number (a U.S. SEC CIK helps the SEC lookup)
              <input name="registration_number" />
            </label>
            <label className="ws-field">
              Jurisdiction
              <input name="jurisdiction" />
            </label>
            <label className="ws-field">
              Website
              <input name="website" placeholder="https://" />
            </label>
            <label className="ws-field">
              Address
              <input name="address" />
            </label>
            <button className="ws-button primary" disabled={add.busy} type="submit">
              Add candidate
            </button>
            <ActionError error={add.error} />
          </form>
        </section>
      )}

      {canWrite && (
        <section className="ws-card">
          <h3>{closed ? "Reopen the entity choice" : "The entity cannot be confirmed or found"}</h3>
          <p>
            {closed
              ? "Reopening clears the choice so a different entity can be chosen. A reason is required and recorded."
              : "Record that the entity could not be confirmed. A reason is required and recorded."}
          </p>
          <label className="ws-field">
            Reason
            <input onChange={(event) => setReason(event.target.value)} value={reason} />
          </label>
          {closed ? (
            <button className="ws-button" disabled={reopen.busy || !reason.trim()} onClick={reopenResolution} type="button">
              Reopen the choice
            </button>
          ) : (
            <button className="ws-button" disabled={unconfirmed.busy || !reason.trim()} onClick={markUnconfirmed} type="button">
              Record as not confirmed
            </button>
          )}
          <ActionError error={reopen.error ?? unconfirmed.error} />
        </section>
      )}
    </div>
  );
}
