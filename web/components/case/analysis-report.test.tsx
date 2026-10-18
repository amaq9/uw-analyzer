import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AnalysisReportView, type AnalysisReportData } from "@/components/case/analysis-report";

const area = (key: string, title: string, status: AnalysisReportData["consolidated_status"], finding: string) => ({
  key,
  title,
  status,
  finding,
  trend: "Weakening",
  why: `${title} text. Cash less debt is -CAD 1m.`,
  flags: status === "WEAK" ? ["Current ratio below 1.0"] : [],
  metrics: [{ label: "Current ratio", current: "1.29x", prior: "1.45x", earlier: "1.60x", change: "down" as const }],
  feeds_draft: true,
});

const report: AnalysisReportData = {
  basis: {
    statements: "uploaded statement fy.pdf",
    periods: ["2026-05-31", "2025-05-31"],
    currency: "CAD",
    units: "Figures shown in millions of CAD unless stated",
    audit_note: "Statements are NOT audited",
    method: "Financial-statement assessment method",
  },
  areas: [
    area("balance_sheet", "Balance sheet strength", "OK", "Satisfactory"),
    area("liquidity", "Liquidity", "WEAK", "Needs attention"),
    area("gearing", "Gearing", "DISTRESSED", "Weak"),
    area("receivables", "Accounts receivable", "NOT_ASSESSED", "Not assessed"),
    area("cash_flow", "Cash flow generation", "OK", "Strong"),
    { ...area("profitability", "Profitability (context)", "WEAK", "Needs attention"), feeds_draft: false },
    { ...area("efficiency", "Efficiency and industry context (context)", "NOT_ASSESSED", "Not assessed"), feeds_draft: false },
  ],
  executive_summary: "Consolidated financial findings: satisfactory. Of the five core areas, 2 are OK.",
  key_concerns: ["Cash flow generation: distressed. Cash from operations fell.", "Not known: Receivables aging."],
  debt_service: [{ label: "Cash from operations over current liabilities", current: "0.31x", prior: "0.44x", earlier: "0.50x", change: "down" }],
  debt_service_notes: ["The debt maturity ladder is not in the figures."],
  stress: [
    { scenario: "As reported", earnings: "CAD 20m", interest_cover: "4.00x", cash_from_operations: "CAD 15m" },
    { scenario: "Revenue down 10%", earnings: "CAD 10m", interest_cover: "2.00x", cash_from_operations: "CAD 5m" },
  ],
  stress_note: "Illustration only. It is not a forecast.",
  consolidated_status: "WEAK",
  consolidated_finding: "Satisfactory",
  consolidated_why: "The core sections are not weak together.",
  red_flags: [
    { text: "Negative shareholders' equity", state: "CLEAR", detail: "Equity is CAD 9m." },
    { text: "Net debt to EBITDA above 3.0x", state: "TRIGGERED", detail: "Net debt is 3.40x EBITDA." },
    { text: "Going-concern language", state: "NOT_ASSESSABLE", detail: "Needs the printed statements." },
  ],
  strengths: ["Balance sheet strength: satisfactory."],
  weaknesses: ["Liquidity: needs attention."],
  watch: ["Current ratio is 1.29x."],
  gaps: ["Receivables aging was not available."],
  other_checks: [{ title: "Sector outlook", state: "NOT_ASSESSED", detail: "Not assessed." }],
  analyzer_version: "1",
};

describe("Step 1 analysis report", () => {
  it("shows what was reviewed, the five areas with colour words, and the consolidated finding", () => {
    render(<AnalysisReportView currency="CAD" report={report} />);
    expect(screen.getByText("uploaded statement fy.pdf")).toBeInTheDocument();
    const glance = screen.getByLabelText("Status of each financial area");
    expect(within(glance).getAllByText("OK").length).toBeGreaterThanOrEqual(2);
    expect(within(glance).getAllByText("Weak").length).toBeGreaterThanOrEqual(2); // chip plus the key
    expect(within(glance).getAllByText("Distressed").length).toBeGreaterThanOrEqual(2);
    expect(within(glance).getAllByText("Not assessed").length).toBeGreaterThanOrEqual(2);
    expect(within(glance).getByText("Consolidated financial findings")).toBeInTheDocument();
  });

  it("opens with an executive summary and lists the key concerns in order", () => {
    render(<AnalysisReportView currency="CAD" report={report} />);
    expect(screen.getByText("Executive summary")).toBeInTheDocument();
    expect(screen.getByText(/Of the five core areas, 2 are OK/)).toBeInTheDocument();
    const concerns = screen.getByText("What matters most, in order").closest("section") as HTMLElement;
    const items = within(concerns).getAllByRole("listitem");
    expect(items[0]).toHaveTextContent(/Cash flow generation: distressed/);
    expect(within(concerns).getByText(/not a ranking of the company/i)).toBeInTheDocument();
  });

  it("marks profitability and efficiency as context that does not change the draft amount", () => {
    render(<AnalysisReportView currency="CAD" report={report} />);
    const glance = screen.getByLabelText("Status of each financial area");
    expect(within(glance).getAllByText(/does not change the draft amount/i)).toHaveLength(2);
    const profitability = document.getElementById("ar-profitability") as HTMLElement;
    expect(within(profitability).getByText(/Context only/)).toBeInTheDocument();
    expect(within(profitability).getAllByText("Two periods before").length).toBeGreaterThan(0);
    expect(within(profitability).getByText("1.60x")).toBeInTheDocument();
  });

  it("shows the debt-service block and a sensitivity that says it is not a forecast", () => {
    render(<AnalysisReportView currency="CAD" report={report} />);
    expect(screen.getByText("Can cash carry the debt falling due?")).toBeInTheDocument();
    expect(screen.getByText("Revenue down 10%")).toBeInTheDocument();
    expect(screen.getByText(/not a forecast/i)).toBeInTheDocument();
    expect(screen.getByText(/debt maturity ladder is not in the figures/i)).toBeInTheDocument();
  });

  it("never shows a colour without its word, and no number is presented as a score", () => {
    const { container } = render(<AnalysisReportView currency="CAD" report={report} />);
    for (const chip of container.querySelectorAll(".st-chip")) {
      expect(chip.textContent).toMatch(/(OK|Weak|Distressed|Not assessed)$/);
    }
    expect(screen.getByText(/not a score or rating of the company/i)).toBeInTheDocument();
  });

  it("gives each area its figures with this period, the period before and the direction", () => {
    render(<AnalysisReportView currency="CAD" report={report} />);
    const liquidity = document.getElementById("ar-liquidity") as HTMLElement;
    expect(within(liquidity).getByText("1.29x")).toBeInTheDocument();
    expect(within(liquidity).getByText("1.45x")).toBeInTheDocument();
    expect(within(liquidity).getByText("▼ Down")).toBeInTheDocument();
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

  it("closes with strengths, weaknesses, what to watch, gaps and the other research areas, with no doubled currency", () => {
    render(<AnalysisReportView currency="CAD" report={report} />);
    for (const label of ["Strengths", "Weaknesses", "What to watch", "Gaps", "Other research areas"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    expect(screen.getByText("Sector outlook")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/CAD CAD/);
  });
});
