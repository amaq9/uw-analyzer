"use client";

import { type FormEvent, useState } from "react";

import type { AnalysisReportData } from "@/components/case/analysis-report";
import type { components } from "@/lib/api/schema";
import { ActionError, useAction, useLoad } from "@/components/use-api";
import { api } from "@/lib/api/client";
import { dateOnly, dateTime, readable } from "@/lib/format";

type Rating = components["schemas"]["PublishedRatingOut"];
type Agency = Rating["agency"];

const AGENCIES: { id: Agency; name: string; example: string }[] = [
  { id: "MOODYS", name: "Moody's", example: "Baa2" },
  { id: "SP", name: "S&P", example: "BBB+" },
  { id: "FITCH", name: "Fitch", example: "BBB" },
];

const OUTLOOKS = [
  ["NOT_STATED", "Not stated"],
  ["STABLE", "Stable"],
  ["POSITIVE", "Positive"],
  ["NEGATIVE", "Negative"],
  ["DEVELOPING", "Developing"],
] as const;

const CHANGES = [
  ["NOT_STATED", "Not stated"],
  ["AFFIRMED", "Affirmed"],
  ["NEW", "First rating"],
  ["UPGRADE", "Upgrade"],
  ["DOWNGRADE", "Downgrade"],
] as const;

/** Local date and time for an input, as the browser wants it. */
function nowLocal() {
  const date = new Date();
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 16);
}

function RecordForm({
  base,
  onDone,
  token,
}: Readonly<{ base: string; onDone: () => void; token: string }>) {
  const action = useAction();
  const [agency, setAgency] = useState<Agency>("MOODYS");
  const [grade, setGrade] = useState("");
  const [outlook, setOutlook] = useState("NOT_STATED");
  const [change, setChange] = useState("NOT_STATED");
  const [underReview, setUnderReview] = useState(false);
  const [lastAction, setLastAction] = useState("");
  const [rationale, setRationale] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [readAt, setReadAt] = useState(nowLocal);
  const [quote, setQuote] = useState("");
  const example = AGENCIES.find((item) => item.id === agency)?.example ?? "";
  const ready = grade.trim() && sourceUrl.trim() && quote.trim() && readAt;

  async function submit(event: FormEvent) {
    event.preventDefault();
    const body: Record<string, unknown> = {
      agency,
      grade: grade.trim(),
      outlook,
      change,
      under_review: underReview,
      source_url: sourceUrl.trim(),
      retrieved_at: new Date(readAt).toISOString(),
      quote: quote.trim(),
    };
    if (lastAction) body.last_action_on = lastAction;
    if (rationale.trim()) body.rationale = rationale.trim();
    const done = await action.run(() => api(token, "POST", base, body));
    if (done) {
      setGrade("");
      setRationale("");
      setQuote("");
      setSourceUrl("");
      setUnderReview(false);
      onDone();
    }
  }

  return (
    <details className="pr-form">
      <summary>Record a published rating</summary>
      <p className="ws-muted">
        Copy what the agency published, and where you read it. A rating needs its source address, the time you read it and the
        agency&apos;s own words. Nothing is inferred. The product does not search for ratings by itself.
      </p>
      <form className="ws-form" onSubmit={submit}>
        <label className="ws-field">
          Agency
          <select onChange={(event) => setAgency(event.target.value as Agency)} value={agency}>
            {AGENCIES.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <label className="ws-field">
          Grade, in the agency&apos;s own wording (for example {example})
          <input onChange={(event) => setGrade(event.target.value)} value={grade} />
        </label>
        <label className="ws-field">
          Outlook
          <select onChange={(event) => setOutlook(event.target.value)} value={outlook}>
            {OUTLOOKS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="ws-field">
          Last action
          <select onChange={(event) => setChange(event.target.value)} value={change}>
            {CHANGES.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="ws-field">
          Date of the last action (optional)
          <input onChange={(event) => setLastAction(event.target.value)} type="date" value={lastAction} />
        </label>
        <label className="pr-check">
          <input checked={underReview} onChange={(event) => setUnderReview(event.target.checked)} type="checkbox" />
          The agency has this rating under review
        </label>
        <label className="ws-field">
          The agency&apos;s stated reasons (optional)
          <textarea onChange={(event) => setRationale(event.target.value)} rows={2} value={rationale} />
        </label>
        <label className="ws-field">
          Source address (https)
          <input onChange={(event) => setSourceUrl(event.target.value)} placeholder="https://…" value={sourceUrl} />
        </label>
        <label className="ws-field">
          When you read it
          <input onChange={(event) => setReadAt(event.target.value)} type="datetime-local" value={readAt} />
        </label>
        <label className="ws-field">
          The agency&apos;s own words (quote, up to 300 characters)
          <textarea maxLength={300} onChange={(event) => setQuote(event.target.value)} required rows={2} value={quote} />
        </label>
        <button className="ws-button primary" disabled={action.busy || !ready} type="submit">
          Record this rating
        </button>
        <ActionError error={action.error} />
      </form>
    </details>
  );
}

/** Published agency opinions, with their sources. External information: never this product's rating and
 *  never an input to the draft. Words only, no colour (ADR 0020). */
export function PublishedRatings({
  analysis,
  canRecord,
  caseId,
  token,
}: Readonly<{ analysis?: AnalysisReportData | null; canRecord: boolean; caseId: string; token: string }>) {
  const base = `/api/v1/cases/${encodeURIComponent(caseId)}/published-ratings`;
  const ratings = useLoad((t, signal) => api<Rating[]>(t, "GET", base, undefined, signal), [caseId]);
  const byAgency = new Map((ratings.data ?? []).map((rating) => [rating.agency, rating]));
  const snapshot = analysis?.published_ratings ?? [];
  const live = ratings.data ?? [];
  const newer =
    analysis !== undefined && analysis !== null && live.some((rating) => !snapshot.some((s) => s.id === rating.id));

  return (
    <section aria-labelledby="pr-title" className="ws-card pr">
      <p className="eyebrow">External information</p>
      <h3 id="pr-title">Published credit ratings</h3>
      <p className="ws-muted">
        These are the agencies&apos; own opinions, recorded with their source. They are not this product&apos;s rating, and they do
        not change the draft recommendation. Moody&apos;s Aaa to Baa3 and S&amp;P or Fitch AAA to BBB- are investment grade.
      </p>
      {ratings.error && (
        <p className="ws-error" role="alert">
          The recorded ratings could not be loaded. {ratings.error.message}
        </p>
      )}
      <div className="ws-table-wrap">
        <table className="ws-table">
          <thead>
            <tr>
              <th>Agency</th>
              <th>Published rating</th>
              <th>Outlook</th>
              <th>Last action</th>
              <th>Reasons and source</th>
            </tr>
          </thead>
          <tbody>
            {AGENCIES.map(({ id, name }) => {
              const rating = byAgency.get(id);
              if (!rating) {
                return (
                  <tr key={id}>
                    <td>{name}</td>
                    <td colSpan={4}>No published rating recorded</td>
                  </tr>
                );
              }
              return (
                <tr key={id}>
                  <td>{name}</td>
                  <td>
                    <strong>{rating.grade}</strong>
                    <small className="ws-muted">{rating.investment_grade ? "Investment grade" : "Below investment grade"}</small>
                  </td>
                  <td>
                    {readable(rating.outlook)}
                    {rating.under_review && <small className="ws-muted">Under review</small>}
                  </td>
                  <td>
                    {rating.change === "NOT_STATED" ? "Not stated" : readable(rating.change)}
                    {rating.last_action_on && <small className="ws-muted">{dateOnly(rating.last_action_on)}</small>}
                  </td>
                  <td>
                    {rating.rationale && <span>{rating.rationale} </span>}
                    <blockquote className="ws-quote">“{rating.quote}”</blockquote>
                    <small className="ws-muted">
                      Read {dateTime(rating.retrieved_at)} by {rating.recorded_by}.{" "}
                      <a href={rating.source_url} rel="noreferrer" target="_blank">
                        Open source
                      </a>
                    </small>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {analysis?.ratings_reconciliation && (
        <p className="pr-compare">
          <strong>Compared with the financial analysis:</strong> {analysis.ratings_reconciliation}
        </p>
      )}
      {newer && (
        <p className="ws-note">
          A rating was recorded after this draft was prepared. Analyse the research again to include it in a new draft.
        </p>
      )}
      {canRecord ? (
        <RecordForm base={base} onDone={ratings.reload} token={token} />
      ) : (
        <p className="ws-muted">Your role cannot record a published rating.</p>
      )}
    </section>
  );
}
