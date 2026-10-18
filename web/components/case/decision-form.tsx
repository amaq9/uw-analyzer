"use client";

import { type FormEvent, useState } from "react";

import { outcomeHeadline, TestPill } from "@/components/case/draft-hero";
import type { DecisionRecord, DraftRecord } from "@/components/case/types";
import { ActionError, useAction } from "@/components/use-api";
import { api } from "@/lib/api/client";
import { dateTime, money, readable } from "@/lib/format";

type Choice = "ADOPT" | "CHANGE" | "REJECT";

function draftLine(draft: Pick<DraftRecord, "outcome" | "band" | "recommended_amount" | "requested_currency">) {
  return draft.outcome === "APPROVE"
    ? `${outcomeHeadline(draft)}: ${money(draft.recommended_amount, draft.requested_currency)}`
    : "Decline";
}

function decisionLine(decision: DecisionRecord) {
  if (decision.final_outcome === "APPROVE") return `Approve ${money(decision.final_amount, decision.currency)}`;
  if (decision.final_outcome === "DECLINE") return "Decline";
  return "No outcome recorded";
}

/** UW Analyzer and decision side by side, so the difference is plain. The decision is the only outcome. */
export function DecisionSummary({ decision, draft }: Readonly<{ decision: DecisionRecord; draft?: DraftRecord }>) {
  const action =
    decision.action === "ADOPT"
      ? "Adopted the UW Analyzer recommendation as written"
      : decision.action === "CHANGE"
        ? "Changed the UW Analyzer recommendation"
        : "Rejected the UW Analyzer recommendation (set aside)";
  return (
    <section aria-labelledby="rec-decision-title" className="rec-decided">
      <div className="rec-hero-top">
        <p className="rec-label">Underwriter decision, recorded by a named person.</p>
        <TestPill />
      </div>
      <h2 id="rec-decision-title">{action}</h2>
      <p className="rec-decided-by">
        Recorded by <strong>{decision.decided_by}</strong> · {dateTime(decision.decided_at)} · cannot be edited
      </p>

      <div className="rec-compare">
        <div className="rec-compare-col">
          <span>The UW Analyzer said</span>
          <strong>{draft ? draftLine(draft) : "See the UW Analyzer recommendation above"}</strong>
        </div>
        <div className="rec-compare-col is-final">
          <span>Actual decision</span>
          <strong>{decisionLine(decision)}</strong>
        </div>
      </div>
      <p className="rec-agree">{decision.agrees ? "Your decision matches the UW Analyzer recommendation." : "Your decision differs from the UW Analyzer recommendation."}</p>
      {decision.reason && (
        <blockquote className="rec-your-reason">
          <span>Your written reason</span>
          {decision.reason}
        </blockquote>
      )}
    </section>
  );
}

const CHOICES: { value: Choice; title: string; hint: string }[] = [
  { value: "ADOPT", title: "Adopt the UW Analyzer recommendation as written", hint: "Your decision becomes the recommendation's outcome and amount." },
  { value: "CHANGE", title: "Change it (different outcome or amount)", hint: "Set your own outcome. You explain why." },
  { value: "REJECT", title: "Reject it (set it aside; no outcome is recorded)", hint: "No outcome is recorded. You explain why." },
];

/** The one place a decision is recorded, by a named person. Never pre-filled with an outcome. */
export function DecisionForm({
  base,
  draft,
  onDone,
  token,
}: Readonly<{ base: string; draft: DraftRecord; onDone: () => void; token: string }>) {
  const action = useAction();
  const [choice, setChoice] = useState<Choice>("ADOPT");
  const [reason, setReason] = useState("");
  const [outcome, setOutcome] = useState<"APPROVE" | "DECLINE">("APPROVE");
  const [amount, setAmount] = useState("");
  const needsReason = choice !== "ADOPT";
  const requested = Number(draft.requested_amount);
  const typed = Number(amount);
  const overRequest = Number.isFinite(requested) && requested > 0 && typed > requested;
  const ready =
    (!needsReason || reason.trim().length > 0) &&
    (choice !== "CHANGE" || outcome === "DECLINE" || (typed > 0 && !overRequest));

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

  const needsAmount = choice === "CHANGE" && outcome === "APPROVE";
  const amountOk = typed > 0 && !overRequest;
  const missing = [
    ...(needsAmount && !amountOk ? ["an amount above zero and not above the amount requested"] : []),
    ...(needsReason && reason.trim().length === 0 ? ["your reason"] : []),
  ];
  const consequence =
    choice === "ADOPT"
      ? `You will record: ${draftLine(draft)}.`
      : choice === "REJECT"
        ? "You will record: the UW Analyzer recommendation set aside, with no outcome."
        : outcome === "DECLINE"
          ? "You will record: Decline."
          : amountOk
            ? `You will record: Approve ${money(amount, draft.requested_currency)}.`
            : overRequest
              ? "That amount cannot be recorded: it is above the amount requested."
              : "Enter the amount you approve.";

  return (
    <section aria-labelledby="rec-decide-title" className="rec-decide">
      <div className="rec-hero-top">
        <p className="rec-label">Underwriter decision</p>
        <TestPill />
      </div>
      <h2 id="rec-decide-title">Your decision on recommendation version {draft.version}</h2>
      <p className="rec-decide-intro">
        The UW Analyzer recommendation above is a recommendation only. Nothing is decided until you record your choice. It is saved under your
        name and cannot be edited afterwards.
      </p>

      <form className="rec-decide-form" onSubmit={submit}>
        <fieldset className="rec-choices">
          <legend>What do you do with the UW Analyzer recommendation?</legend>
          {CHOICES.map((item) => (
            <label className={`rec-choice${choice === item.value ? " is-selected" : ""}`} key={item.value}>
              <input checked={choice === item.value} name="choice" onChange={() => setChoice(item.value)} type="radio" />
              <span>
                <strong>{item.title}</strong>
                <small>{item.hint}</small>
              </span>
            </label>
          ))}
        </fieldset>

        {choice === "CHANGE" && (
          <div className="rec-change">
            <label className="ws-field">
              Your outcome
              <select aria-label="Your outcome" onChange={(event) => setOutcome(event.target.value as "APPROVE" | "DECLINE")} value={outcome}>
                <option value="APPROVE">Approve an amount</option>
                <option value="DECLINE">Decline</option>
              </select>
            </label>
            {outcome === "APPROVE" && (
              <label className="ws-field">
                Amount ({draft.requested_currency ?? "currency of the request"}; not above the amount requested)
                <input inputMode="decimal" onChange={(event) => setAmount(event.target.value)} value={amount} />
                {overRequest && (
                  <small className="rec-field-error">
                    That is above the amount requested ({money(draft.requested_amount, draft.requested_currency)}).
                  </small>
                )}
              </label>
            )}
          </div>
        )}

        {needsReason && (
          <label className="ws-field">
            Reason (required)
            <textarea onChange={(event) => setReason(event.target.value)} required rows={3} value={reason} />
          </label>
        )}

        <div className="rec-confirm">
          <div aria-live="polite">
            <p>{consequence}</p>
            {missing.length > 0 && <small className="rec-missing">Still needed: {missing.join(" and ")}.</small>}
          </div>
          <button className="ws-button primary" disabled={action.busy || !ready} type="submit">
            Record my decision ({readable(choice).toLowerCase()})
          </button>
        </div>
        <ActionError error={action.error} />
      </form>
    </section>
  );
}
