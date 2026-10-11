"use client";

import { type FormEvent, useState } from "react";

import type { components } from "@/lib/api/schema";
import { ActionError, useAction } from "@/components/use-api";
import { api } from "@/lib/api/client";

type Extraction = components["schemas"]["ExtractionOut"];

const UNITS = [
  { value: "units", label: "Single units (for example 1,250,000)" },
  { value: "thousands", label: "Thousands (for example 1,250)" },
  { value: "millions", label: "Millions (for example 1.25)" },
];

function toNumber(text: string): number | null {
  const cleaned = text.trim().replaceAll(",", "");
  if (!cleaned) return null;
  const negative = /^\(.*\)$/.test(cleaned);
  const value = Number(cleaned.replace(/[()]/g, ""));
  if (!Number.isFinite(value)) return Number.NaN;
  return negative ? -value : value;
}

/** Check, correct and confirm the figures suggested from an uploaded document. */
export function StatementReview({
  base,
  documentId,
  extraction,
  onConfirmed,
  token,
}: Readonly<{
  base: string;
  documentId: string;
  extraction: Extraction;
  onConfirmed: () => void;
  token: string;
}>) {
  const columns = Math.max(extraction.periods.length, 1);
  const found = Object.fromEntries(extraction.rows.map((row) => [row.metric, row]));
  const [values, setValues] = useState<Record<string, string[]>>(() =>
    Object.fromEntries(
      extraction.metrics.map((metric) => [
        metric.metric,
        Array.from({ length: columns }, (_, index) => {
          const suggested = found[metric.metric]?.values[index];
          return suggested === null || suggested === undefined ? "" : String(suggested);
        }),
      ]),
    ),
  );
  const [ends, setEnds] = useState<string[]>(() =>
    Array.from({ length: columns }, (_, index) => extraction.period_end_guesses[index] ?? ""),
  );
  const [unit, setUnit] = useState<string>(extraction.unit_guess ?? "");
  const [currency, setCurrency] = useState(extraction.currency_guess ?? "");
  const [audit, setAudit] = useState("");
  const [notes, setNotes] = useState("");
  const action = useAction();
  const [done, setDone] = useState(false);

  const parsed = ends.map((_, column) => {
    const figures: Record<string, number | null> = {};
    let invalid = false;
    for (const metric of extraction.metrics) {
      const value = toNumber(values[metric.metric][column] ?? "");
      if (Number.isNaN(value)) invalid = true;
      figures[metric.metric] = value;
    }
    const count = Object.values(figures).filter((value) => value !== null).length;
    return { figures, invalid, count };
  });
  const used = parsed.map((period, index) => ({ ...period, end: ends[index] })).filter((period) => period.count > 0);
  const problems: string[] = [];
  if (!unit) problems.push("Choose the unit the document uses.");
  if (!/^[A-Za-z]{3}$/.test(currency)) problems.push("Enter the three-letter currency code, for example CAD.");
  if (!audit) problems.push("Say whether the statements are audited, reviewed or unaudited.");
  if (used.length === 0) problems.push("Enter figures for at least one period.");
  if (used.some((period) => !period.end)) problems.push("Give the period end date for each period that has figures.");
  if (used.some((period) => period.count < 3)) problems.push("Give at least three figures for each period you use.");
  if (parsed.some((period) => period.invalid)) problems.push("One of the figures is not a number.");

  async function confirm(event: FormEvent) {
    event.preventDefault();
    const result = await action.run(() =>
      api(token, "POST", `${base}/statements`, {
        document_id: documentId,
        currency: currency.toUpperCase(),
        unit,
        audit_status: audit,
        notes: notes.trim() || null,
        periods: used.map((period) => ({ period_end: period.end, figures: period.figures })),
      }),
    );
    if (result) {
      setDone(true);
      onConfirmed();
    }
  }

  if (done) {
    return (
      <p className="ws-note" role="status">
        The figures were confirmed under your name and will be used when you run the analysis.
      </p>
    );
  }

  return (
    <form className="ws-form ws-wide" onSubmit={confirm}>
      <h4>Check the figures from {extraction.filename}</h4>
      <p className="ws-muted">{extraction.notice}</p>
      {extraction.notes.map((note) => (
        <p className="ws-note" key={note}>
          {note}
        </p>
      ))}

      <div className="ws-split">
        <label className="ws-field">
          Unit the document uses
          <select onChange={(event) => setUnit(event.target.value)} value={unit}>
            <option value="">Choose…</option>
            {UNITS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="ws-field">
          Currency (three letters)
          <input maxLength={3} onChange={(event) => setCurrency(event.target.value)} value={currency} />
        </label>
        <label className="ws-field">
          The statements are
          <select onChange={(event) => setAudit(event.target.value)} value={audit}>
            <option value="">Choose…</option>
            <option value="AUDITED">Audited</option>
            <option value="REVIEWED">Reviewed (not a full audit)</option>
            <option value="UNAUDITED">Unaudited (management accounts)</option>
          </select>
        </label>
      </div>

      <div className="ws-table-wrap">
        <table className="ws-table">
          <thead>
            <tr>
              <th>Figure</th>
              <th>Label found in the document</th>
              {ends.map((end, index) => (
                <th key={index}>
                  {extraction.periods[index] ?? `Period ${index + 1}`}
                  <input
                    aria-label={`Period ${index + 1} end date`}
                    onChange={(event) => setEnds(ends.map((value, i) => (i === index ? event.target.value : value)))}
                    type="date"
                    value={end}
                  />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {extraction.metrics.map((metric) => (
              <tr key={metric.metric}>
                <td>{metric.label}</td>
                <td>
                  <small className="ws-muted">{found[metric.metric]?.label ?? "Not found: type it if the document has it"}</small>
                </td>
                {ends.map((_, column) => (
                  <td key={column}>
                    <input
                      aria-label={`${metric.label}, period ${column + 1}`}
                      inputMode="decimal"
                      onChange={(event) =>
                        setValues({
                          ...values,
                          [metric.metric]: values[metric.metric].map((value, i) => (i === column ? event.target.value : value)),
                        })
                      }
                      value={values[metric.metric][column] ?? ""}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="ws-muted">
        Outflows may be shown as negative or in brackets; the analysis treats capital spending, dividends and buybacks as
        amounts paid out. Leave a box empty if the document does not give that figure.
      </p>
      <label className="ws-field">
        Note (optional)
        <input onChange={(event) => setNotes(event.target.value)} value={notes} />
      </label>
      {problems.length > 0 && (
        <ul className="ws-bullets">
          {problems.map((problem) => (
            <li key={problem}>{problem}</li>
          ))}
        </ul>
      )}
      <button className="ws-button primary" disabled={action.busy || problems.length > 0} type="submit">
        Confirm these figures
      </button>
      <ActionError error={action.error} />
    </form>
  );
}
