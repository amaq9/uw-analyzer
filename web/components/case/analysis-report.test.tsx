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
  consolidated_why: "The four core dimensions (liquidity, profitability, leverage, cash flow): 2 OK, 1 weak, 1 distressed.",
  key_concerns: ["Leverage: distressed. Debt to equity is high.", "Not known: Receivables aging."],
  red_flags: [
    { text: "Negative shareholders' equity", state: "CLEAR", detail: "Equity is CAD 9m." },
    { text: "Net debt to EBITDA above 3.0x", state: "TRIGGERED", detail: "Net debt is 3.40x EBITDA." },
    { text: "Going-concern language", state: "NOT_ASSESSABLE", detail: "Needs the printed statements." },
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
    expect(screen.getByText("Executive summary")).toBeInTheDocument();
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
    expect(within(glance).getAllByText(/does not change the draft amount/i)).toHaveLength(1);
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

  it("lists the red-flag checklist as prompts, with the checks that could not be made", () => {
    render(<AnalysisReportView currency="CAD" report={report} />);
    expect(screen.getByText("3 prompts for the underwriter's attention")).toBeInTheDocument();
    expect(screen.getByText("Look closer")).toBeInTheDocument();
    expect(screen.getByText("Clear")).toBeInTheDocument();
    expect(screen.getByText("Not assessable")).toBeInTheDocument();
    expect(screen.getByText(/prompts, not pass or fail tests/i)).toBeInTheDocument();
  });

  it("shows the debt-service block and a sensitivity that says it is not a forecast", () => {
    render(<AnalysisReportView currency="CAD" report={report} />);
    expect(screen.getByText("Can cash carry the debt falling due?")).toBeInTheDocument();
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
