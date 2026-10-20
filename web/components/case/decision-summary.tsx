import { outcomeHeadline, TestPill } from "@/components/case/draft-hero";
import type { DecisionRecord, DraftRecord } from "@/components/case/types";
import type { CaseRecord } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { dateOnly, money, shorten } from "@/lib/format";

type Analysis = components["schemas"]["AnalysisReport"];
type Area = components["schemas"]["AreaReport"];

const AGENCY: Record<string, string> = { MOODYS: "Moody's", SP: "S&P", FITCH: "Fitch" };
const STANDING: Record<Area["status"], string> = { OK: "OK", WEAK: "weak", DISTRESSED: "distressed", NOT_ASSESSED: "not assessed" };

/** The figures a chief executive asks for, by the area and label the analysis already uses. */
const KEY_FIGURES: ReadonlyArray<readonly [string, string, string]> = [
  ["Revenue", "profitability", "Revenue"],
  ["Net margin", "profitability", "Net margin"],
  ["Cash from operations", "cash_flow", "Cash from operations"],
  ["Free cash flow", "cash_flow", "Free cash flow (after capital spending)"],
  ["Current ratio", "liquidity", "Current ratio"],
  ["Debt to equity", "leverage", "Debt to equity"],
  ["Net debt to EBITDA", "leverage", "Net debt to EBITDA"],
  ["Interest cover", "leverage", "Interest cover (EBIT over interest)"],
];

/** A clean result from the annual report, said plainly. Only a result with no concern is listed as a strength. */
const FILING_STRENGTHS: Record<string, string> = {
  "Auditor's opinion": "Clean (unqualified) audit opinion",
  "Going concern": "No going-concern warning in the annual report",
  "Loan covenants": "The annual report states the company complied with its loan covenants",
  "Internal control over financial reporting": "Internal controls over financial reporting reported as effective",
};

function metric(analysis: Analysis, area: string, label: string) {
  return analysis.areas.find((a) => a.key === area)?.metrics?.find((m) => m.label === label);
}

function plainLabel(label: string) {
  const short = label.replace(/\s*\(.*\)$/, "");
  return short.charAt(0).toLowerCase() + short.slice(1);
}

/** "Balance sheet and leverage strong: debt to equity 0.74x, net debt to EBITDA 0.44x, ...": the key figures first,
 * then the other measures that have a reference. */
function areaStrength(area: Area) {
  const key = KEY_FIGURES.filter(([, a]) => a === area.key).map(([, , label]) => label);
  const usable = (area.metrics ?? []).filter((m) => m.current && m.current !== "Not disclosed");
  const ordered = [
    ...key.flatMap((label) => usable.filter((m) => m.label === label)),
    ...usable.filter((m) => m.reference && !key.includes(m.label)),
  ];
  const measures = ordered.slice(0, 3).map((m) => `${plainLabel(m.label)} ${m.current}`);
  return `${area.title} ${area.finding.toLowerCase()}${measures.length ? `: ${measures.join(", ")}` : ""}`;
}

function strengths(analysis: Analysis) {
  const out = analysis.areas.filter((a) => a.feeds_draft && a.status === "OK").map(areaStrength);
  for (const finding of analysis.notes_review?.findings ?? []) {
    const line = FILING_STRENGTHS[finding.title];
    if (line && finding.state === "NO_CONCERN") out.push(line);
  }
  const checks = analysis.other_checks ?? [];
  if (checks.some((c) => c.title.startsWith("Sanctions list") && c.state === "CLEAR")) {
    out.push("No match on the U.S. sanctions list (OFAC, name search)");
  }
  if (checks.some((c) => c.title.startsWith("Entity register") && c.state === "FOUND")) {
    out.push("Legal entity confirmed in the global LEI register");
  }
  return out;
}

/** The warning signs that fired. Those about the rating agencies are left to the agencies' own section. */
function risks(analysis: Analysis) {
  return analysis.red_flags
    .filter((f) => f.state === "TRIGGERED" && !/\bagency\b/i.test(f.text))
    .map((f) => `${f.text.replace(/, or negative$/, "")}: ${f.detail.replace(/\.$/, "")}`)
    .slice(0, 6);
}

function day(value: string) {
  return new Date(value).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

function rating(r: components["schemas"]["PublishedRatingOut"]) {
  const bits = [`${AGENCY[r.agency] ?? r.agency} ${r.grade}`];
  if (r.change === "DOWNGRADE") bits.push("downgraded");
  if (r.change === "UPGRADE") bits.push("upgraded");
  if (r.outlook !== "NOT_STATED") bits.push(`${r.outlook.toLowerCase()} outlook`);
  if (r.under_review) bits.push("under review");
  if (r.last_action_on) bits.push(`last action ${dateOnly(r.last_action_on)}`);
  return bits.join(", ") + (r.source_kind === "AGENCY_SITE" ? "" : " (as reported in the press)");
}

/** Everything after the headline's first sentence: the amount is already in the decision box above it. */
function inBrief(headline: string) {
  const rest = headline.split(/(?<=\.) /).slice(1).join(" ");
  return rest || headline;
}

function share(amount: string | null, requested: string | null) {
  const a = Number(amount);
  const r = Number(requested);
  return Number.isFinite(a) && Number.isFinite(r) && r > 0 ? Math.round((a / r) * 100) : null;
}

/**
 * The UW Analyzer Decision Summary: one printable page a chief executive can read. The underwriter's decision, why,
 * the figures behind it, strengths and risks, and what the review could not cover. It leaves out the underwriter's
 * working list. Every line is taken from the stored analysis, so it says nothing the recommendation does not.
 */
export function DecisionSummary({
  decided,
  draft,
  record,
}: Readonly<{ decided: DecisionRecord | null; draft: DraftRecord; record: CaseRecord }>) {
  const currency = draft.requested_currency;
  const analysis = draft.analysis as Analysis | null | undefined;
  const brief = analysis?.executive_brief;
  const name = record.legal_name ?? record.trading_name ?? "Unnamed case";

  const outcome = decided ? decided.final_outcome : draft.outcome;
  const amount = decided ? decided.final_amount : draft.recommended_amount;
  const portion = outcome === "APPROVE" ? share(amount, draft.requested_amount) : null;
  const reduced = draft.outcome === "APPROVE" && draft.band === "REDUCED" && draft.factors.length > 0;
  const headline = !decided
    ? `${outcomeHeadline(draft)}${draft.outcome === "APPROVE" ? `: ${money(draft.recommended_amount, currency)}` : ""}`
    : outcome === "APPROVE"
      ? `Approve ${money(amount, decided.currency ?? currency)}`
      : outcome === "DECLINE"
        ? "Decline"
        : "No outcome recorded";
  const matches = decided
    ? decided.agrees
      ? "In line with the UW Analyzer recommendation."
      : `The UW Analyzer recommended: ${outcomeHeadline(draft).toLowerCase()}${
          draft.outcome === "APPROVE" ? `, ${money(draft.recommended_amount, currency)}` : ""
        }.`
    : null;

  const figures = analysis
    ? KEY_FIGURES.map(([shown, area, label]) => [shown, metric(analysis, area, label)] as const).filter(([, m]) => m)
    : [];
  const core = analysis?.areas.filter((a) => a.feeds_draft) ?? [];
  const good = analysis ? strengths(analysis) : [];
  const bad = analysis ? risks(analysis) : [];
  const ratings = analysis?.published_ratings ?? [];
  const stress = brief?.sections.find((s) => s.heading === "If sales fall")?.text;
  const notCovered = (analysis?.other_checks ?? [])
    .filter((c) => c.state === "NOT_SEARCHED" || c.state === "INCOMPLETE" || c.state === "NOT_ASSESSED")
    .map((c) => (c.state === "INCOMPLETE" ? `${c.title} (incomplete)` : c.title));

  return (
    <article aria-label="UW Analyzer Decision Summary" className="final-report ceo">
      <header className="final-head">
        <div>
          <p className="rec-label">UW Analyzer Decision Summary</p>
          <h2>{name}</h2>
          <p className="ws-muted">
            {[record.jurisdiction, record.industry].filter(Boolean).join(" · ") || "Jurisdiction not provided"}
            {decided ? ` · decided ${day(decided.decided_at)}` : ""}
          </p>
        </div>
        <TestPill />
      </header>

      <section aria-label="Decision" className="final-decision">
        <span>{decided ? "Underwriter decision" : "UW Analyzer recommendation (not a decision)"}</span>
        <strong>{headline}</strong>
        <p>
          {portion !== null ? `${portion}% of the ${money(draft.requested_amount, currency)} requested. ` : `${money(draft.requested_amount, currency)} requested. `}
          {decided ? `Decided by ${decided.decided_by}. ${matches}` : "No decision has been recorded yet."}
        </p>
        {decided?.reason && <p>Reason given: {decided.reason}</p>}
        {reduced && (
          <p>
            Below the request because:{" "}
            {draft.factors.map((factor) => shorten(factor.explanation, currency).replace(/\.$/, "")).join("; ")}.
          </p>
        )}
      </section>

      {brief && (
        <section>
          <h3>In brief</h3>
          <p>{inBrief(brief.headline)}</p>
        </section>
      )}

      {figures.length > 0 && (
        <section>
          <h3>Key figures</h3>
          <table className="ceo-figures">
            <thead>
              <tr>
                <th scope="col">Measure</th>
                <th scope="col">Latest year</th>
                <th scope="col">Year before</th>
              </tr>
            </thead>
            <tbody>
              {figures.map(([shown, m]) => (
                <tr key={shown}>
                  <th scope="row">{shown}</th>
                  <td>{m?.current}</td>
                  <td>{m?.prior}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {core.length > 0 && (
            <p className="ceo-standing">
              {core.map((a) => `${a.title}: ${STANDING[a.status]}`).join(" · ")}
            </p>
          )}
        </section>
      )}

      {(good.length > 0 || bad.length > 0) && (
        <div className="ceo-cols">
          <section>
            <h3>Strengths</h3>
            <ul className="final-list">
              {good.length ? good.map((line) => <li key={line}>{line}</li>) : <li>None stood out in the analysis.</li>}
            </ul>
          </section>
          <section>
            <h3>Risks</h3>
            <ul className="final-list">
              {bad.length ? bad.map((line) => <li key={line}>{line}</li>) : <li>No warning signs were triggered.</li>}
            </ul>
          </section>
        </div>
      )}

      {ratings.length > 0 && (
        <section>
          <h3>Rating agencies</h3>
          <ul className="final-list">
            {ratings.map((r) => (
              <li key={r.id}>{rating(r)}</li>
            ))}
          </ul>
        </section>
      )}

      {stress && (
        <section>
          <h3>If sales fall</h3>
          <p>{stress}</p>
        </section>
      )}

      {notCovered.length > 0 && (
        <p className="ceo-scope">
          <b>Not covered by this review:</b> {notCovered.join("; ")}.
        </p>
      )}

      <footer className="final-foot">
        <p>
          From UW Analyzer recommendation v{draft.version} (policy v{draft.policy_version}), {day(draft.created_at)}; every figure
          traces to its source on the recommendation tab. Test product: internal evaluation only, not communicated to any
          customer and creates no commitment.
        </p>
      </footer>
    </article>
  );
}
