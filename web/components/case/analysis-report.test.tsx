import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AnalysisReportView, type AnalysisReportData } from "@/components/case/analysis-report";

type Area = AnalysisReportData["areas"][number];

const area = (key: string, title: string, status: Area["status"], finding: string, feeds = true): Area => ({
  key,
  title,
  status,
  finding,
  trend: "Weakening",
  why: `${title} text. Cash less debt is -CAD 1m.`,
  flags: status === "WEAK" ? ["Current ratio below 1.0"] : [],
  metrics: [
    { label: "Current ratio", current: "1.29x", prior: "1.45x", earlier: "1.60x", change: "down", reference: "1.5 to 2.0" },
  ],
  feeds_draft: feeds,
});

const report: AnalysisReportData = {
  basis: {
    statements: "uploaded statement fy.pdf",
    periods: ["2026-05-31", "2025-05-31"],
    currency: "CAD",
    units: "Figures shown in millions of CAD unless stated",
    audit_note: "Statements are NOT audited",
    method: "Analyst framework",
  },
  executive_summary: "Consolidated financial findings: weak. The four core dimensions: 1 OK, 1 weak, 1 distressed.",
  areas: [
    area("liquidity", "Liquidity", "WEAK", "Concerning"),
    area("profitability", "Profitability", "OK", "Adequate"),
    area("leverage", "Leverage", "DISTRESSED", "Critical"),
    area("cash_flow", "Cash flow", "OK", "Strong"),
    area("efficiency", "Efficiency and sector", "NOT_ASSESSED", "Not assessed", false),
  ],
  consolidated_status: "WEAK",
  consolidated_finding: "Satisfactory",
  consolidated_why: "The four core dimensions (profitability, liquidity, balance sheet and leverage, cash flow): 2 OK, 1 weak, 1 distressed.",
  key_concerns: ["Leverage: distressed. Debt to equity is high.", "Not known: Receivables aging."],
  red_flags: [
    { text: "Negative shareholders' equity", state: "CLEAR", detail: "Equity is CAD 9m.", result: "Condition not met" },
    { text: "Net debt to EBITDA above 3.0x", state: "TRIGGERED", detail: "Net debt is 3.40x EBITDA.", result: "Above threshold" },
    { text: "Going-concern language", state: "NOT_ASSESSABLE", detail: "Needs the printed statements.", result: "Not assessable" },
  ],
  debt_service: [
    { label: "Cash from operations over current liabilities", current: "0.31x", prior: "0.44x", earlier: "0.50x", change: "down", reference: "" },
  ],
  debt_service_notes: ["The debt maturity ladder is not in the figures."],
  stress: [
    { scenario: "As reported", earnings: "CAD 20m", interest_cover: "4.00x", cash_from_operations: "CAD 15m" },
    { scenario: "Revenue down 10%", earnings: "CAD 10m", interest_cover: "2.00x", cash_from_operations: "CAD 5m" },
  ],
  stress_note: "Illustration only. It is not a forecast.",
  strengths: ["Profitability: adequate."],
  weaknesses: ["Leverage: critical."],
  watch: ["Current ratio is 1.29x."],
  gaps: ["Receivables aging was not available."],
  other_checks: [{ title: "Sector outlook", state: "NOT_ASSESSED", detail: "Not assessed." }],
  analyzer_version: "2",
};

describe("Step 1 analysis report", () => {
  it("shows what was reviewed, the five dimensions with colour words, and the consolidated finding", () => {
    render(<AnalysisReportView currency="CAD" report={report} />);
    expect(screen.getByText("uploaded statement fy.pdf")).toBeInTheDocument();
    const glance = screen.getByLabelText("Status of each financial area");
    expect(within(glance).getAllByText("OK").length).toBeGreaterThanOrEqual(3);
    expect(within(glance).getAllByText("Weak").length).toBeGreaterThanOrEqual(2); // chips plus the key
    expect(within(glance).getAllByText("Distressed").length).toBeGreaterThanOrEqual(2);
    expect(within(glance).getAllByText("Not assessed").length).toBeGreaterThanOrEqual(1);
    expect(within(glance).getByText("Consolidated financial findings")).toBeInTheDocument();
    for (const title of ["Liquidity", "Profitability", "Leverage", "Cash flow", "Efficiency and sector"]) {
      expect(within(glance).getByText(title)).toBeInTheDocument();
    }
  });

  it("opens with an executive summary and lists the key concerns in order", () => {
    render(<AnalysisReportView currency="CAD" report={report} />);
    expect(screen.getByText("Financial summary")).toBeInTheDocument();
    expect(screen.getByText(/The four core dimensions: 1 OK/)).toBeInTheDocument();
    const concerns = screen.getByText("What matters most, in order").closest("section") as HTMLElement;
    const items = within(concerns).getAllByRole("listitem");
    expect(items[0]).toHaveTextContent(/Leverage: distressed/);
    expect(within(concerns).getByText(/not a ranking of the company/i)).toBeInTheDocument();
  });

  it("shows the framework's finding word beside each colour, and marks efficiency as context", () => {
    render(<AnalysisReportView currency="CAD" report={report} />);
    const leverage = document.getElementById("ar-leverage") as HTMLElement;
    expect(within(leverage).getByText(/Critical · Weakening/)).toBeInTheDocument();
    const liquidity = document.getElementById("ar-liquidity") as HTMLElement;
    expect(within(liquidity).getByText(/Concerning · Weakening/)).toBeInTheDocument();
    const glance = screen.getByLabelText("Status of each financial area");
    expect(within(glance).getAllByText(/does not change the recommended amount/i)).toHaveLength(1);
    const efficiency = document.getElementById("ar-efficiency") as HTMLElement;
    expect(within(efficiency).getByText(/Shown for context/)).toBeInTheDocument();
  });

  it("never shows a colour without its word, and no number is presented as a score", () => {
    const { container } = render(<AnalysisReportView currency="CAD" report={report} />);
    for (const chip of container.querySelectorAll(".st-chip")) {
      expect(chip.textContent).toMatch(/(OK|Weak|Distressed|Not assessed)$/);
    }
    expect(screen.getByText(/not a score or rating of the company/i)).toBeInTheDocument();
  });

  it("gives each dimension its figures: three periods, the direction and the reference range", () => {
    render(<AnalysisReportView currency="CAD" report={report} />);
    const liquidity = document.getElementById("ar-liquidity") as HTMLElement;
    expect(within(liquidity).getByText("1.29x")).toBeInTheDocument();
    expect(within(liquidity).getByText("1.45x")).toBeInTheDocument();
    expect(within(liquidity).getByText("1.60x")).toBeInTheDocument();
    expect(within(liquidity).getByText("▼ Down")).toBeInTheDocument();
    expect(within(liquidity).getByText("1.5 to 2.0")).toBeInTheDocument();
    expect(within(liquidity).getByText("Reference range (indicative)")).toBeInTheDocument();
    expect(within(liquidity).getByText("Current ratio below 1.0")).toBeInTheDocument();
    expect(liquidity.className).toContain("st-weak-edge");
  });

  it("shows the prompts that need a look first and keeps the rest one click away", () => {
    render(<AnalysisReportView currency="CAD" report={report} />);
    const checklist = screen.getByText("3 prompts for the underwriter's attention").closest("section") as HTMLElement;
    const open = within(checklist).getAllByRole("table")[0];
    expect(within(open).getByText("Net debt to EBITDA above 3.0x")).toBeInTheDocument();
    expect(within(open).queryByText("Negative shareholders' equity")).not.toBeInTheDocument();
    const more = within(checklist).getByText(/Show the other 2 prompts/);
    expect(more.closest("details")).not.toHaveAttribute("open");
    expect(within(more.closest("details") as HTMLElement).getByText("Negative shareholders' equity")).toBeInTheDocument();
  });

  it("says so when no prompt needs a look", () => {
    const calm = { ...report, red_flags: report.red_flags.filter((flag) => flag.state !== "TRIGGERED") };
    render(<AnalysisReportView currency="CAD" report={calm} />);
    expect(screen.getByText("No figure crossed the usual lines.")).toBeInTheDocument();
  });

  it("lists the red-flag checklist as prompts, with the checks that could not be made", () => {
    render(<AnalysisReportView currency="CAD" report={report} />);
    expect(screen.getByText("3 prompts for the underwriter's attention")).toBeInTheDocument();
    expect(screen.getByText("Above threshold")).toBeInTheDocument();
    expect(screen.getByText("Condition not met")).toBeInTheDocument();
    expect(screen.getByText("Not assessable")).toBeInTheDocument();
    expect(screen.getByText(/prompts, not pass or fail tests/i)).toBeInTheDocument();
  });

  it("shows the debt-service block and a sensitivity that says it is not a forecast", () => {
    render(<AnalysisReportView currency="CAD" report={report} />);
    expect(screen.getByText("Can cash carry the debt falling due?")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "If revenue falls" })).toBeInTheDocument();
    expect(screen.getByText("Revenue down 10%")).toBeInTheDocument();
    expect(screen.getByText(/not a forecast/i)).toBeInTheDocument();
    expect(screen.getByText(/debt maturity ladder is not in the figures/i)).toBeInTheDocument();
  });

  it("closes with strengths, weaknesses, what to watch, gaps and the other research areas, with no doubled currency", () => {
    render(<AnalysisReportView currency="CAD" report={report} />);
    for (const label of ["Strengths", "Weaknesses", "What to watch", "Gaps", "Other research areas"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    expect(screen.getByText("Sector outlook")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/CAD CAD/);
  });
});


describe("Step 1 notes, definitions and threshold wording", () => {
  const notes: NonNullable<AnalysisReportData["notes_review"]> = {
    source: "Acme 10-K for the year ended 2026-05-31, filed 2026-07-15",
    url: "https://www.sec.gov/Archives/edgar/data/111/000000000026000001/acme.htm",
    filed: "2026-07-15",
    sha256: "a".repeat(64),
    characters: 123456,
    summary: "Concerns stated in the filing: loan covenants. Read the quotes.",
    findings: [
      {
        topic: "COVENANTS",
        title: "Loan covenants",
        state: "CONCERN",
        summary: "The filing states a covenant breach, waiver or default.",
        quotes: [{ text: "The Company was not in compliance with the leverage covenant.", where: null }],
      },
      {
        topic: "GOING_CONCERN",
        title: "Going concern",
        state: "NO_CONCERN",
        summary: "Searched the whole filing: no going-concern warning was found.",
        quotes: [],
      },
    ],
  };

  it("shows what the filing's notes say, in its own words, with a link to the filing", () => {
    render(<AnalysisReportView currency="CAD" report={{ ...report, notes_review: notes }} />);
    const section = screen.getByLabelText("Notes and auditor's report");
    expect(within(section).getByRole("heading", { name: "What the filing says" })).toBeInTheDocument();
    expect(within(section).getByText("Concern stated")).toBeInTheDocument();
    expect(within(section).getByText("No concern stated")).toBeInTheDocument();
    expect(within(section).getByText(/not in compliance with the leverage covenant/)).toBeInTheDocument();
    expect(within(section).getByRole("link", { name: "Open the filing" })).toHaveAttribute("href", notes.url);
    expect(within(section).getByText(/never changes the recommended amount/i)).toBeInTheDocument();
  });

  it("says plainly when the printed filing was not read, and what to do", () => {
    render(<AnalysisReportView currency="CAD" report={{ ...report, notes_review: null }} />);
    const section = screen.getByLabelText("Notes and auditor's report");
    expect(within(section).getByText("The printed 10-K was not read in this run")).toBeInTheDocument();
    expect(within(section).getByText(/Run the research again/)).toBeInTheDocument();
  });

  it("keeps definitions out of the gaps and shows them under their own heading", () => {
    render(
      <AnalysisReportView
        currency="CAD"
        report={{
          ...report,
          gaps: ["Receivables aging was not available.", "Figure derived: EBIT is pre-tax income less net interest income"],
          definitions: ["Net debt is financial debt plus leases, less cash."],
        }}
      />,
    );
    const defined = screen.getByLabelText("How the figures were defined");
    expect(within(defined).getByText("Net debt is financial debt plus leases, less cash.")).toBeInTheDocument();
    expect(within(defined).getByText("EBIT is pre-tax income less net interest income")).toBeInTheDocument();
    const gaps = screen.getByText("Gaps").closest("div") as HTMLElement;
    expect(within(gaps).getByText("Receivables aging was not available.")).toBeInTheDocument();
    expect(within(gaps).queryByText(/Figure derived/)).not.toBeInTheDocument();
  });

  it("words each check by its result, with red when past the line and green when not", () => {
    const flags = [
      { text: "Debt to equity above 2.5", state: "CLEAR", detail: "Debt to equity is 0.74x.", result: "Not above threshold" },
      { text: "Net debt to EBITDA above 3.0x", state: "TRIGGERED", detail: "Net debt is 3.40x EBITDA.", result: "Above threshold" },
    ] as AnalysisReportData["red_flags"];
    render(<AnalysisReportView currency="CAD" report={{ ...report, red_flags: flags }} />);
    expect(screen.getByText("Not above threshold")).toHaveClass("is-clear");
    expect(screen.getByText("Above threshold")).toHaveClass("is-triggered");
    expect(screen.getByText(/Show the other 1 prompts \(not above or below the threshold, or not assessable\)/)).toBeInTheDocument();
  });
});


describe("Step 1 paragraphs and the cash conversion cycle", () => {
  const cycle: NonNullable<AnalysisReportData["cash_cycle"]> = {
    periods: ["2026-05-31", "2025-05-31", "2024-05-31"],
    summary: "The company collects from customers in 46.7 days (was 37.2 days). Cash is therefore tied up for 100.4 days.",
    notes: ["Inventory is taken from the finished-goods figure (total inventory is not tagged)."],
    status: "WEAK",
    finding: "Concerning",
    trend: "Weakening",
    flags: ["Change in the cash conversion cycle: +8.0 days"],
    standing:
      "The cash conversion cycle is rated Concerning (shown as Weak) because it is judged by its weakest measure. What to do: Ask for the receivables ageing. This is context only: it does not change the recommended amount.",
    rows: [
      { key: "dso", label: "Days sales outstanding (DSO)", current: "46.7 days", prior: "37.2 days", earlier: "31.5 days", movement: "Longer by 9.5 days (slower collection)", direction: "worse" },
      { key: "dio", label: "Days inventory outstanding (DIO)", current: "No inventory reported", prior: "No inventory reported", earlier: null, movement: "Not applicable: no inventory", direction: "unknown" },
      { key: "dpo", label: "Days payables outstanding (DPO)", current: "49.6 days", prior: "47.9 days", earlier: "36.5 days", movement: "Longer by 1.7 days (paying suppliers later)", direction: "better" },
      { key: "ccc", label: "Cash conversion cycle (CCC = DSO + DIO - DPO)", current: "-2.9 days", prior: "-10.7 days", earlier: null, movement: "Longer by 7.8 days (more cash tied up)", direction: "worse" },
    ],
  };

  it("explains each financial area's standing in a short paragraph", () => {
    const withSummary = {
      ...report,
      areas: report.areas.map((a, i) => (i === 0 ? { ...a, summary: "Liquidity is rated Concerning because cash from operations is 0.23x of current liabilities." } : a)),
    };
    render(<AnalysisReportView currency="CAD" report={withSummary} />);
    expect(screen.getByText("Why this standing")).toBeInTheDocument();
    expect(screen.getByText(/rated Concerning because cash from operations is 0.23x/)).toBeInTheDocument();
  });

  it("shows the cash conversion cycle with each measure, its movement and a blank DIO that says why", () => {
    render(<AnalysisReportView currency="CAD" report={{ ...report, cash_cycle: cycle }} />);
    const section = screen.getByLabelText("Cash conversion cycle");
    expect(within(section).getByRole("heading", { name: "Cash conversion cycle" })).toBeInTheDocument();
    expect(within(section).getByText("Weak")).toBeInTheDocument(); // the same signal as the other financial areas
    expect(section).toHaveClass("st-weak-edge");
    expect(within(section).getByText("Why this standing, and what to do")).toBeInTheDocument();
    expect(within(section).getByText(/What to do: Ask for the receivables ageing/)).toBeInTheDocument();
    expect(within(section).getByText("Change in the cash conversion cycle: +8.0 days")).toBeInTheDocument();
    expect(within(section).getByText("46.7 days")).toBeInTheDocument();
    expect(within(section).getAllByText("No inventory reported").length).toBeGreaterThanOrEqual(1);
    expect(within(section).getByText("Not applicable: no inventory")).toBeInTheDocument();
    expect(within(section).getByText(/Longer by 9.5 days \(slower collection\)/)).toBeInTheDocument();
    const worse = within(section).getAllByText(/worse for cash/, { selector: "strong" });
    expect(worse).toHaveLength(2); // days sales and the cycle itself
    expect(worse[0]).toHaveClass("is-worse");
    expect(within(section).getByText(/better for cash/, { selector: "strong" })).toHaveClass("is-better");
    expect(within(section).getByText(/finished-goods figure/)).toBeInTheDocument();
    expect(within(section).getAllByText(/does not change the recommended amount/).length).toBeGreaterThanOrEqual(1);
  });

  it("shows no cash conversion section when there is nothing to calculate", () => {
    render(<AnalysisReportView currency="CAD" report={{ ...report, cash_cycle: null }} />);
    expect(screen.queryByLabelText("Cash conversion cycle")).not.toBeInTheDocument();
  });
});
