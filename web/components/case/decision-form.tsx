"use client";

import { type FormEvent, useState } from "react";

import type { DecisionRecord, DraftRecord } from "@/components/case/types";
import { ActionError, useAction } from "@/components/use-api";
import { api } from "@/lib/api/client";
import { dateTime, money, readable } from "@/lib/format";

export function DecisionSummary({ decision }: Readonly<{ decision: DecisionRecord }>) {
  return (
    <section className="ws-card ws-decision">
      <p className="eyebrow">Underwriter decision</p>
      <h3>Recorded by {decision.decided_by}</h3>
      <p>
        {decision.action === "ADOPT" && "The draft was adopted as written."}
        {decision.action === "CHANGE" && "The draft was changed."}
        {decision.action === "REJECT" && "The draft was set aside; no outcome was recorded."}
      </p>
      {decision.final_outcome && (
        <p>
          <strong>
            {decision.final_outcome === "APPROVE"
              ? `Approved amount: ${money(decision.final_amount, decision.currency)}`
              : "Declined"}
          </strong>
        </p>
      )}
      {decision.reason && <p>Reason: {decision.reason}</p>}
      <p className="ws-muted">
        {dateTime(decision.decided_at)} · {decision.agrees ? "Agrees with the draft" : "Differs from the draft"}
      </p>
    </section>
  );
}

/** The one place a decision is recorded, by a named person. Never pre-filled with an outcome. */
export function DecisionForm({
  base,
  draft,
  onDone,
  token,
}: Readonly<{ base: string; draft: DraftRecord; onDone: () => void; token: string }>) {
  const action = useAction();
  const [choice, setChoice] = useState<"ADOPT" | "CHANGE" | "REJECT">("ADOPT");
  const [reason, setReason] = useState("");
  const [outcome, setOutcome] = useState<"APPROVE" | "DECLINE">("APPROVE");
  const [amount, setAmount] = useState("");
  const needsReason = choice !== "ADOPT";
  const ready =
    (!needsReason || reason.trim().length > 0) && (choice !== "CHANGE" || outcome === "DECLINE" || Number(amount) > 0);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const body: Record<string, unknown> = { action: choice };
    if (needsReason) body.reason = reason.trim();
    if (choice === "CHANGE") {
      body.final_outcome = outcome;
      if (outcome === "APPROVE") body.final_amount = amount;
    }
    const done = await action.run(() => api(token, "POST", `${base}/${draft.id}/decision`, body));
    if (done) onDone();
  }

  return (
    <section className="ws-card ws-decision">
      <p className="eyebrow">Underwriter decision</p>
      <h3>Your decision on draft version {draft.version}</h3>
      <p>
        The draft above is a recommendation only. Adopt it, change it, or set it aside. Your choice is recorded under your
        name and cannot be edited afterwards.
      </p>
      <form className="ws-form" onSubmit={submit}>
        <fieldset className="ws-radios">
          <legend>What do you do with the draft?</legend>
          {(
            [
              ["ADOPT", "Adopt the draft as written"],
              ["CHANGE", "Change it (different outcome or amount)"],
              ["REJECT", "Reject it (set it aside; no outcome is recorded)"],
            ] as const
          ).map(([value, label]) => (
            <label key={value}>
              <input checked={choice === value} name="choice" onChange={() => setChoice(value)} type="radio" />
              {label}
            </label>
          ))}
        </fieldset>
        {choice === "CHANGE" && (
          <>
            <label className="ws-field">
              Your outcome
              <select onChange={(event) => setOutcome(event.target.value as "APPROVE" | "DECLINE")} value={outcome}>
                <option value="APPROVE">Approve an amount</option>
                <option value="DECLINE">Decline</option>
              </select>
            </label>
            {outcome === "APPROVE" && (
              <label className="ws-field">
                Amount ({draft.requested_currency ?? "currency of the request"}; not above the amount requested)
                <input inputMode="decimal" onChange={(event) => setAmount(event.target.value)} value={amount} />
              </label>
            )}
          </>
        )}
        {needsReason && (
          <label className="ws-field">
            Reason (required)
            <textarea onChange={(event) => setReason(event.target.value)} required rows={3} value={reason} />
          </label>
        )}
        <button className="ws-button primary" disabled={action.busy || !ready} type="submit">
          Record my decision ({readable(choice).toLowerCase()})
        </button>
        <ActionError error={action.error} />
      </form>
    </section>
  );
}
