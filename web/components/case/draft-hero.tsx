import type { DraftRecord } from "@/components/case/types";
import { dateTime, money, readable, shorten } from "@/lib/format";

/** The only wording of an outcome on the recommendation screen. Always inside the labelled draft. */
export function outcomeHeadline(draft: Pick<DraftRecord, "outcome" | "band">) {
  if (draft.outcome === "DECLINE") return "Decline";
  return draft.band === "FULL" ? "Approve the full amount requested" : "Approve a reduced amount";
}

function share(amount: string | null, requested: string | null) {
  const a = Number(amount);
  const r = Number(requested);
  if (!Number.isFinite(a) || !Number.isFinite(r) || r <= 0) return null;
  return Math.max(0, Math.min(100, (a / r) * 100));
}

export function TestPill() {
  return <span className="rec-test-pill">Test product</span>;
}

/** Draft outcome, the amount set against the request, and how the number was reached. */
export function DraftHero({ draft }: Readonly<{ draft: DraftRecord }>) {
  const currency = draft.requested_currency;
  const approve = draft.outcome === "APPROVE";
  const portion = approve ? share(draft.recommended_amount, draft.requested_amount) : null;

  return (
    <section aria-labelledby="rec-hero-title" className={`rec-hero ${approve ? "is-approve" : "is-decline"}`}>
      <div className="rec-hero-top">
        <p className="rec-label">Draft recommendation for the underwriter. Not a decision.</p>
        <TestPill />
      </div>

      <div className="rec-hero-main">
        <div>
          <p className="rec-kicker">Draft outcome</p>
          <h2 id="rec-hero-title">{outcomeHeadline(draft)}</h2>
          {approve ? (
            <p className="rec-amount">
              {money(draft.recommended_amount, currency)}
              <span> of {money(draft.requested_amount, currency)} requested</span>
            </p>
          ) : (
            <p className="rec-amount muted">No amount is recommended. {money(draft.requested_amount, currency)} was requested.</p>
          )}
          <p className="rec-summary">{shorten(draft.summary, currency)}</p>
        </div>

        {approve && portion !== null && (
          <figure className="rec-meter">
            <div
              aria-label={`Draft amount is ${Math.round(portion)} percent of the amount requested`}
              className="rec-meter-track"
              role="img"
            >
              <div className="rec-meter-fill" style={{ width: `${portion}%` }} />
            </div>
            <figcaption>
              <span>{Math.round(portion)}% of the amount requested</span>
              <span>{draft.band === "FULL" ? "Full amount" : "Reduced amount"}</span>
            </figcaption>
          </figure>
        )}
      </div>

      <ol aria-label="How the draft was reached" className="rec-path">
        <li>
          <span>Requested</span>
          <strong>{money(draft.requested_amount, currency)}</strong>
        </li>
        <li>
          <span>Analyst proposed</span>
          <strong>{draft.ai_proposed_amount ? money(draft.ai_proposed_amount, currency) : "No amount"}</strong>
        </li>
        <li>
          <span>Policy v{draft.policy_version}</span>
          <strong>{draft.rule_codes.length ? draft.rule_codes.map((code) => readable(code)).join(", ") : "Rules applied"}</strong>
        </li>
        <li>
          <span>Draft</span>
          <strong>{approve ? money(draft.recommended_amount, currency) : "Decline"}</strong>
        </li>
      </ol>
    </section>
  );
}

/** Step 1 result: what the analysis found, each finding tied to its sources. */
export function AnalysisFindings({ draft }: Readonly<{ draft: DraftRecord }>) {
  const currency = draft.requested_currency;
  return (
    <section className="ws-card rec-reasons">
      <p className="eyebrow">Sources</p>
      <h3>The sources behind each finding</h3>
      <ol className="rec-reason-list">
        {draft.reasons.map((reason, index) => (
          <li key={`${index}-${reason.text}`}>
            <p className="rec-reason-text">{shorten(reason.text, currency)}</p>
            <details>
              <summary>
                {reason.evidence.length} source{reason.evidence.length === 1 ? "" : "s"}
              </summary>
              <ul className="rec-evidence">
                {reason.evidence.map((item, i) => (
                  <li key={`${item.kind}-${item.document_id ?? item.url}-${i}`}>
                    <blockquote>“{item.quote}”</blockquote>
                    <small>
                      {item.kind === "web" ? "Web source" : "Case document"}
                      {item.retrieved_at ? ` · accessed ${dateTime(item.retrieved_at)}` : ""}
                      {item.location ? ` · ${item.location}` : ""}{" "}
                      {item.kind === "web" && item.url && (
                        <a href={item.url} rel="noreferrer" target="_blank">
                          Open source
                        </a>
                      )}
                    </small>
                  </li>
                ))}
              </ul>
            </details>
          </li>
        ))}
      </ol>
    </section>
  );
}

/** Step 2 detail: what lowered the amount, what is not known, and what was recorded with the draft. */
export function DraftBasis({ draft }: Readonly<{ draft: DraftRecord }>) {
  const currency = draft.requested_currency;
  const gaps = [...new Set(draft.information_gaps)];
  return (
    <div className="rec-basis">
      <section className="ws-card">
        <p className="eyebrow">What lowered the amount</p>
        {draft.factors.length ? (
          <ul className="ws-bullets">
            {draft.factors.map((factor) => (
              <li key={factor.code}>
                <strong>{readable(factor.code)}.</strong> {shorten(factor.explanation, currency)}
              </li>
            ))}
          </ul>
        ) : (
          <p className="ws-muted">Nothing lowered the amount.</p>
        )}
      </section>

      <section className="ws-card">
        <p className="eyebrow">What is not known</p>
        {gaps.length ? (
          <ul className="ws-bullets">
            {gaps.map((gap) => (
              <li key={gap}>{gap}</li>
            ))}
          </ul>
        ) : (
          <p className="ws-muted">No information gaps were recorded.</p>
        )}
        {draft.limitations.length > 0 && <p className="ws-muted">{draft.limitations.join(" ")}</p>}
      </section>

      <section className="ws-card rec-versions">
        <p className="eyebrow">Recorded with this draft</p>
        <dl>
          <div>
            <dt>Draft version</dt>
            <dd>{draft.version}</dd>
          </div>
          <div>
            <dt>Prepared</dt>
            <dd>{dateTime(draft.created_at)}</dd>
          </div>
          <div>
            <dt>Prepared by</dt>
            <dd>{draft.created_by}</dd>
          </div>
          <div>
            <dt>Model</dt>
            <dd>{draft.source.model}</dd>
          </div>
          <div>
            <dt>Method version</dt>
            <dd>{draft.source.skill_version}</dd>
          </div>
          <div>
            <dt>Policy version</dt>
            <dd>{draft.policy_version}</dd>
          </div>
        </dl>
      </section>
    </div>
  );
}

/** A numbered step heading, so the screen reads in order: 1 analysis, 2 draft, 3 decision. */
export function StepHeading({ id, number, title, note }: Readonly<{ id: string; number: number; title: string; note: string }>) {
  return (
    <header className="rec-step-heading" id={id}>
      <span className="rec-step-number">{number}</span>
      <div>
        <h2>
          Step {number} · {title}
        </h2>
        <p>{note}</p>
      </div>
    </header>
  );
}
