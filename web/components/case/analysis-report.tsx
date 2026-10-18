import type { components } from "@/lib/api/schema";
import { readable, shorten } from "@/lib/format";
import { splitGaps } from "@/lib/gaps";

export type AnalysisReportData = components["schemas"]["AnalysisReport"];
type Status = AnalysisReportData["consolidated_status"];

/** The only place status colours are used (ADR 0018). The word and a symbol always come with the colour. */
const STATUS: Record<Status, { word: string; mark: string; className: string }> = {
  OK: { word: "OK", mark: "✓", className: "st-ok" },
  WEAK: { word: "Weak", mark: "!", className: "st-weak" },
  DISTRESSED: { word: "Distressed", mark: "✕", className: "st-distressed" },
  NOT_ASSESSED: { word: "Not assessed", mark: "–", className: "st-na" },
};

export function StatusChip({ status }: Readonly<{ status: Status }>) {
  const item = STATUS[status];
  return (
    <span className={`st-chip ${item.className}`}>
      <span aria-hidden="true">{item.mark}</span>
      {item.word}
    </span>
  );
}

const CHANGE = { up: "▲ Up", down: "▼ Down", flat: "● Flat", unknown: "–" } as const;

/** The result is worded by the server ("Above threshold", "Not above threshold", ...). This is only the fallback. */
const FLAG_FALLBACK = { TRIGGERED: "Condition met", CLEAR: "Condition not met", NOT_ASSESSABLE: "Not assessable" } as const;
const CHECK_WORD = {
  CLEAR: "Clear",
  FOUND: "Found",
  NOT_SEARCHED: "Not searched",
  INCOMPLETE: "Incomplete",
  NOT_ASSESSED: "Not assessed",
} as const;

function List({ items, empty }: Readonly<{ items: string[]; empty: string }>) {
  if (!items.length) return <p className="ws-muted">{empty}</p>;
  return (
    <ul className="ws-bullets">
      {items.map((item, index) => (
        <li key={`${index}-${item}`}>{item}</li>
      ))}
    </ul>
  );
}

function FlagTable({ flags, t }: Readonly<{ flags: AnalysisReportData["red_flags"]; t: (text: string) => string }>) {
  if (flags.length === 0) return null;
  return (
    <div className="ws-table-wrap">
      <table className="ws-table">
        <thead>
          <tr>
            <th>Check</th>
            <th>Result</th>
            <th>Detail</th>
          </tr>
        </thead>
        <tbody>
          {flags.map((flag) => (
            <tr key={flag.text}>
              <td>{flag.text}</td>
              <td>
                <span className={`ar-flag-state is-${flag.state.toLowerCase()}`}>{flag.result || FLAG_FALLBACK[flag.state]}</span>
              </td>
              <td>{t(flag.detail)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const DIRECTION = {
  better: { word: "better for cash", className: "is-better" },
  worse: { word: "worse for cash", className: "is-worse" },
  same: { word: "no change", className: "is-same" },
  unknown: { word: "", className: "is-same" },
} as const;

/** Days sales, inventory and payables outstanding and the cash conversion cycle, with how each moved. */
function CashCycleSection({ cycle }: Readonly<{ cycle: AnalysisReportData["cash_cycle"] | null }>) {
  if (!cycle) return null;
  const periods = cycle.periods ?? [];
  return (
    <section aria-label="Cash conversion cycle" className={`ws-card ar-area ${STATUS[cycle.status].className}-edge`} id="ar-cash-cycle">
      <header className="ar-area-head">
        <h3>Cash conversion cycle</h3>
        <div className="ar-area-status">
          <StatusChip status={cycle.status} />
          <span className="ws-muted">Shown for context · {cycle.finding} · {cycle.trend}</span>
        </div>
      </header>
      {cycle.standing && (
        <div className="ar-summary-para">
          <p className="eyebrow">Why this standing, and what to do</p>
          <p>{cycle.standing}</p>
        </div>
      )}
      <p className="ar-why">{cycle.summary}</p>
      {(cycle.flags ?? []).length > 0 && (
        <ul className="ar-flags">
          {(cycle.flags ?? []).map((flag) => (
            <li key={flag}>{flag}</li>
          ))}
        </ul>
      )}
      <div className="ws-table-wrap">
        <table className="ws-table ar-metrics">
          <thead>
            <tr>
              <th>Measure</th>
              <th>This period</th>
              <th>Period before</th>
              <th>Two periods before</th>
              <th>Movement on the year before</th>
            </tr>
          </thead>
          <tbody>
            {cycle.rows.map((row) => (
              <tr className={row.key === "ccc" ? "cc-total" : undefined} key={row.key}>
                <td>{row.label}</td>
                <td>
                  <strong>{row.current}</strong>
                </td>
                <td>{row.prior ?? "No earlier year"}</td>
                <td>{row.earlier ?? "No earlier year"}</td>
                <td>
                  {row.movement}
                  {DIRECTION[row.direction].word && (
                    <strong className={`cc-direction ${DIRECTION[row.direction].className}`}> · {DIRECTION[row.direction].word}</strong>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {periods.length > 0 && <p className="ws-muted">Year-end balances for the periods ending {periods.join(", ")}.</p>}
      {(cycle.notes ?? []).length > 0 && <List empty="" items={cycle.notes ?? []} />}
      <p className="ws-muted">
        Days sales outstanding is receivables over revenue; days inventory outstanding is inventory over cost of sales; days
        payables outstanding is trade payables over cost of sales; the cycle is sales days plus inventory days less payables days.
        Shown for context: it does not change the recommended amount.
      </p>
    </section>
  );
}

const NOTE_STATE = {
  CONCERN: { word: "Concern stated", className: "is-concern" },
  NO_CONCERN: { word: "No concern stated", className: "is-clear" },
  INFO: { word: "For you to read", className: "is-info" },
  NOT_FOUND: { word: "Not in the filing", className: "is-none" },
} as const;

/** What the printed 10-K's notes and auditor's report say, in the filing's own words. */
function NotesSection({ review }: Readonly<{ review: AnalysisReportData["notes_review"] | null }>) {
  if (!review) {
    return (
      <section aria-label="Notes and auditor's report" className="ws-card">
        <p className="eyebrow">Notes and auditor&apos;s report</p>
        <h3>The printed 10-K was not read in this run</h3>
        <p className="ws-muted">
          The notes and the auditor&apos;s report can show a going-concern warning, a covenant breach or an auditor&apos;s qualification
          that the figures cannot. Run the research again so the filing text is retrieved, then analyse again.
        </p>
      </section>
    );
  }
  return (
    <section aria-label="Notes and auditor's report" className="ws-card">
      <p className="eyebrow">Notes and auditor&apos;s report</p>
      <h3>What the filing says</h3>
      <p>{review.summary}</p>
      <p className="ws-muted">
        Read from {review.source}. {review.characters.toLocaleString("en-US")} characters of text.{" "}
        {review.url && (
          <a href={review.url} rel="noreferrer" target="_blank">
            Open the filing
          </a>
        )}
      </p>
      <div className="ws-table-wrap">
        <table className="ws-table">
          <thead>
            <tr>
              <th>Topic</th>
              <th>Result</th>
              <th>What the filing says</th>
            </tr>
          </thead>
          <tbody>
            {(review.findings ?? []).map((finding) => (
              <tr key={finding.topic}>
                <td>{finding.title}</td>
                <td>
                  <span className={`ar-note-state ${NOTE_STATE[finding.state].className}`}>{NOTE_STATE[finding.state].word}</span>
                </td>
                <td>
                  {finding.summary}
                  {(finding.quotes ?? []).map((quote) => (
                    <blockquote className="ws-quote" key={quote.text}>
                      “{quote.text}”{quote.where ? ` (${quote.where})` : ""}
                    </blockquote>
                  ))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="ws-muted">
        The quotes are the filing&apos;s own sentences, found by text search. Read the filing for anything the search could not
        classify. This never changes the recommended amount.
      </p>
    </section>
  );
}

/** Step 1 in full: scope, the five dimensions with their figures, the red-flag checklist, the closing view, other checks. */
export function AnalysisReportView({ currency, report }: Readonly<{ currency?: string | null; report: AnalysisReportData }>) {
  const t = (text: string) => shorten(text, currency);
  return (
    <div className="ws-stack ar">
      <section className="ws-card">
        <p className="eyebrow">What was reviewed</p>
        <dl className="ws-facts">
          <div>
            <dt>Statements</dt>
            <dd>{report.basis.statements}</dd>
          </div>
          <div>
            <dt>Periods</dt>
            <dd>{(report.basis.periods ?? []).join(", ") || "None"}</dd>
          </div>
          <div>
            <dt>Currency and units</dt>
            <dd>
              {report.basis.currency} · {report.basis.units}
            </dd>
          </div>
          <div>
            <dt>Audit status</dt>
            <dd>{report.basis.audit_note}</dd>
          </div>
        </dl>
        <p className="ws-muted">
          Method: {report.basis.method} (analyzer v{report.analyzer_version}). Reference ranges are the framework&apos;s own and
          are indicative: no verified peer data is used.
        </p>
      </section>

      <section className="ws-card ar-summary">
        <p className="eyebrow">Financial summary</p>
        <p className="ar-summary-text">{t(report.executive_summary)}</p>
      </section>

      <section aria-label="Status of each financial area" className="ar-overview">
        <div className="ar-overview-head">
          <div>
            <p className="eyebrow">The analyst&apos;s reading</p>
            <h3>Financial areas at a glance</h3>
          </div>
          <ul aria-label="Colour key" className="ar-key">
            <li>
              <StatusChip status="OK" /> in good order
            </li>
            <li>
              <StatusChip status="WEAK" /> needs attention
            </li>
            <li>
              <StatusChip status="DISTRESSED" /> seriously weak
            </li>
          </ul>
        </div>
        <div className="ar-tiles">
          {report.areas.map((area) => (
            <a className={`ar-tile${area.feeds_draft ? "" : " is-context"}`} href={`#ar-${area.key}`} key={area.key}>
              <span>{area.title}</span>
              <StatusChip status={area.status} />
              <small>{area.feeds_draft ? area.trend : "Context only: does not change the recommended amount"}</small>
            </a>
          ))}
          {report.cash_cycle && (
            <a className="ar-tile is-context" href="#ar-cash-cycle">
              <span>Cash conversion cycle</span>
              <StatusChip status={report.cash_cycle.status} />
              <small>Context only: does not change the recommended amount</small>
            </a>
          )}
          <div className="ar-tile is-total">
            <span>Consolidated financial findings</span>
            <StatusChip status={report.consolidated_status} />
            <small>{report.consolidated_why}</small>
          </div>
        </div>
        <p className="ws-muted">
          This is a description of the evidence in words and colour. It is not a score or rating of the company and it is not the
          decision.
        </p>
      </section>

      {(report.key_concerns ?? []).length > 0 && (
        <section className="ws-card ar-concerns">
          <p className="eyebrow">Key concerns</p>
          <h3>What matters most, in order</h3>
          <ol className="ws-bullets">
            {(report.key_concerns ?? []).map((concern, index) => (
              <li key={`${index}-${concern}`}>{t(concern)}</li>
            ))}
          </ol>
          <p className="ws-muted">Ordered by how far each point departs from the usual lines. It is not a ranking of the company.</p>
        </section>
      )}

      {report.areas.map((area) => (
        <section className={`ws-card ar-area ${STATUS[area.status].className}-edge`} id={`ar-${area.key}`} key={area.key}>
          <header className="ar-area-head">
            <h3>{area.title}</h3>
            <div className="ar-area-status">
              <StatusChip status={area.status} />
              <span className="ws-muted">
                {area.feeds_draft ? `${area.finding} · ${area.trend}` : `Shown for context · ${area.finding}`}
              </span>
            </div>
          </header>
          {area.summary && (
            <div className="ar-summary-para">
              <p className="eyebrow">Why this standing</p>
              <p>{area.summary}</p>
            </div>
          )}
          <p className="ar-why">{t(area.why)}</p>
          {(area.flags ?? []).length > 0 && (
            <ul className="ar-flags">
              {(area.flags ?? []).map((flag) => (
                <li key={flag}>{flag}</li>
              ))}
            </ul>
          )}
          {(area.metrics ?? []).length > 0 && (
            <div className="ws-table-wrap">
              <table className="ws-table ar-metrics">
                <thead>
                  <tr>
                    <th>Figure</th>
                    <th>This period</th>
                    <th>Period before</th>
                    <th>Two periods before</th>
                    <th>Change</th>
                    <th>Reference range (indicative)</th>
                  </tr>
                </thead>
                <tbody>
                  {(area.metrics ?? []).map((metric) => (
                    <tr key={metric.label}>
                      <td>{metric.label}</td>
                      <td>
                        <strong>{metric.current}</strong>
                      </td>
                      <td>{metric.prior}</td>
                      <td>{metric.earlier ?? "No earlier year"}</td>
                      <td>{CHANGE[metric.change]}</td>
                      <td>{metric.reference || "–"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      ))}

      <CashCycleSection cycle={report.cash_cycle ?? null} />

      <section className="ws-card">
        <p className="eyebrow">Red-flag checklist</p>
        <h3>{report.red_flags.length} prompts for the underwriter&apos;s attention</h3>
        <p className="ws-muted">These are prompts, not pass or fail tests. In red: the figure is past the usual line, so look closer. In green: it is not.</p>
        <FlagTable flags={report.red_flags.filter((flag) => flag.state === "TRIGGERED")} t={t} />
        {report.red_flags.every((flag) => flag.state !== "TRIGGERED") && (
          <p className="ar-flag-none">No figure crossed the usual lines.</p>
        )}
        <details className="ar-more">
          <summary>
            Show the other {report.red_flags.filter((flag) => flag.state !== "TRIGGERED").length} prompts (not above or below the
            threshold, or not assessable)
          </summary>
          <FlagTable flags={report.red_flags.filter((flag) => flag.state !== "TRIGGERED")} t={t} />
        </details>
      </section>

      <NotesSection review={report.notes_review ?? null} />

      {((report.debt_service ?? []).length > 0 || (report.stress ?? []).length > 0) && (
        <section className="ws-card">
          <p className="eyebrow">Cash flow and debt-service capacity</p>
          <h3>Can cash carry the debt falling due?</h3>
          {(report.debt_service ?? []).length > 0 && (
            <div className="ws-table-wrap">
              <table className="ws-table ar-metrics">
                <thead>
                  <tr>
                    <th>Figure</th>
                    <th>This period</th>
                    <th>Period before</th>
                    <th>Two periods before</th>
                  </tr>
                </thead>
                <tbody>
                  {(report.debt_service ?? []).map((metric) => (
                    <tr key={metric.label}>
                      <td>{metric.label}</td>
                      <td>
                        <strong>{metric.current}</strong>
                      </td>
                      <td>{metric.prior}</td>
                      <td>{metric.earlier ?? "No earlier year"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <List empty="" items={report.debt_service_notes ?? []} />
          {(report.stress ?? []).length > 0 && (
            <>
              <h4>If revenue falls</h4>
              <div className="ws-table-wrap">
                <table className="ws-table ar-metrics">
                  <thead>
                    <tr>
                      <th>Scenario</th>
                      <th>Operating profit</th>
                      <th>Interest cover</th>
                      <th>Cash from operations</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(report.stress ?? []).map((row) => (
                      <tr key={row.scenario}>
                        <td>{row.scenario}</td>
                        <td>{row.earnings}</td>
                        <td>{row.interest_cover}</td>
                        <td>{row.cash_from_operations}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {report.stress_note && <p className="ws-muted">{report.stress_note}</p>}
            </>
          )}
        </section>
      )}

      <section aria-label="Credit-style view" className="ar-view">
        <div className="ws-card">
          <p className="eyebrow">Strengths</p>
          <List empty="None recorded." items={(report.strengths ?? []).map(t)} />
        </div>
        <div className="ws-card">
          <p className="eyebrow">Weaknesses</p>
          <List empty="None recorded." items={(report.weaknesses ?? []).map(t)} />
        </div>
        <div className="ws-card">
          <p className="eyebrow">What to watch</p>
          <List empty="Nothing specific." items={(report.watch ?? []).map(t)} />
        </div>
        <div className="ws-card">
          <p className="eyebrow">Gaps</p>
          <List empty="None recorded." items={splitGaps(report.gaps ?? [], report.definitions ?? []).gaps} />
        </div>
      </section>

      <section aria-label="How the figures were defined" className="ws-card">
        <p className="eyebrow">How the figures were defined</p>
        <p className="ws-muted">Method, not missing information.</p>
        <List empty="None recorded." items={splitGaps(report.gaps ?? [], report.definitions ?? []).definitions} />
      </section>

      <section className="ws-card">
        <p className="eyebrow">Other research areas</p>
        <h3>What else was checked, and what was not</h3>
        <div className="ws-table-wrap">
          <table className="ws-table">
            <thead>
              <tr>
                <th>Area</th>
                <th>Result</th>
                <th>Detail</th>
              </tr>
            </thead>
            <tbody>
              {(report.other_checks ?? []).map((check) => (
                <tr key={check.title}>
                  <td>{check.title}</td>
                  <td>{CHECK_WORD[check.state] ?? readable(check.state)}</td>
                  <td>{check.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
