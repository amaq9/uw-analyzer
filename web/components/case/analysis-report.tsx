import type { components } from "@/lib/api/schema";
import { readable, shorten } from "@/lib/format";

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

const FLAG_WORD = { TRIGGERED: "Look closer", CLEAR: "Clear", NOT_ASSESSABLE: "Not assessable" } as const;
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

/** Step 1 in full: scope, the five areas with their figures, the red-flag checklist, the closing view, other checks. */
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
          Method: {report.basis.method} (analyzer v{report.analyzer_version}). Benchmarks are not used. Profitability is context
          only.
        </p>
      </section>

      <section className="ws-card ar-summary">
        <p className="eyebrow">Executive summary</p>
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
              <small>{area.feeds_draft ? area.trend : "Context only: does not change the draft amount"}</small>
            </a>
          ))}
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
                {area.feeds_draft ? `Analyzer finding: ${area.finding} · ${area.trend}` : `Context only · ${area.trend}`}
              </span>
            </div>
          </header>
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
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      ))}

      <section className="ws-card">
        <p className="eyebrow">Red-flag checklist</p>
        <h3>{report.red_flags.length} prompts for the underwriter&apos;s attention</h3>
        <p className="ws-muted">These are prompts, not pass or fail tests. “Look closer” means the figure crossed the usual line.</p>
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
              {report.red_flags.map((flag) => (
                <tr key={flag.text}>
                  <td>{flag.text}</td>
                  <td>
                    <span className={`ar-flag-state is-${flag.state.toLowerCase()}`}>{FLAG_WORD[flag.state]}</span>
                  </td>
                  <td>{t(flag.detail)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

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
              <h4>If revenue fell and costs did not</h4>
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
          <List empty="None recorded." items={report.gaps ?? []} />
        </div>
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
