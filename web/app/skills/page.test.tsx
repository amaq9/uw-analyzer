import { render, screen, within } from "@testing-library/react";
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

  it("shows the five dimensions in their required order, numbered, each with what the review includes", () => {
    renderSkillsPage();

    const section = screen.getByRole("region", { name: "Five dimensions, reviewed in order" });
    const titles = within(section).getAllByRole("heading", { level: 3 }).map((heading) => heading.textContent);
    expect(titles).toEqual(["Profitability", "Liquidity", "Balance sheet and leverage", "Cash flow", "Efficiency and sector"]);
    expect(within(section).getAllByText("Review includes")).toHaveLength(5);
    expect(within(section).getByText("5 required dimensions")).toBeInTheDocument();
    expect(section.querySelectorAll(".track-node")).toHaveLength(5);
  });

  it("groups what the enhanced skill adds into corroboration, diagnostics and stress testing", () => {
    renderSkillsPage();

    const section = screen.getByRole("region", { name: "Corroboration, context and stress testing" });
    const groups = within(section).getAllByRole("heading", { level: 3 }).map((heading) => heading.textContent);
    expect(groups).toEqual(["External corroboration", "Operating diagnostics", "Stress testing and context"]);
    const items = within(section).getAllByRole("heading", { level: 4 }).map((heading) => heading.textContent);
    expect(items).toEqual([
      "Published third-party credit ratings",
      "Notes and auditor's report",
      "Cash conversion cycle",
      "Warning signs",
      "Revenue decline scenario",
      "Screening and reporting context",
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
