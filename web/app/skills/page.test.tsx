import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SessionProvider } from "@/components/session-provider";

import SkillsPage from "./page";

function renderSkillsPage() {
  return render(
    <SessionProvider>
      <SkillsPage />
    </SessionProvider>,
  );
}

describe("financial statement assessment skill, enhanced", () => {
  it("names the enhanced skill", () => {
    renderSkillsPage();

    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Financial StatementAssessment, Enhanced");
    expect(screen.getByText("Enhanced · with published ratings")).toBeInTheDocument();
  });

  it("shows the five dimensions in their required order, then what the enhanced skill adds", () => {
    renderSkillsPage();

    const headings = screen.getAllByRole("heading", { level: 3 }).map((heading) => heading.textContent);
    expect(headings).toEqual([
      "Profitability",
      "Liquidity",
      "Balance sheet and leverage",
      "Cash flow",
      "Efficiency and sector",
      "Published credit ratings",
      "Notes and auditor's report",
      "Cash conversion cycle",
      "Warning signs",
      "If sales fall",
      "Screening and context",
    ]);
  });

  it("says the skill is in use and links to the cases where it runs", () => {
    renderSkillsPage();

    expect(screen.getByText("In use")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open cases/i })).toHaveAttribute("href", "/cases");
    expect(screen.queryByRole("button", { name: /run assessment/i })).not.toBeInTheDocument();
    expect(screen.getByText(/financial-statement-assessment-enhanced · analyzer v2 · recommendation policy v1\.1/)).toBeInTheDocument();
  });

  it("makes decision and evidence boundaries explicit", () => {
    renderSkillsPage();

    expect(screen.getByText(/a recommendation for the underwriter, never a decision: a named person decides/i)).toBeInTheDocument();
    expect(screen.getByText(/missing figures stay not disclosed, never estimated/i)).toBeInTheDocument();
    expect(screen.getByText(/agency ratings are shown for information and never change the amount/i)).toBeInTheDocument();
    expect(screen.getByText(/indicative context is not verified peer evidence/i)).toBeInTheDocument();
  });
});
