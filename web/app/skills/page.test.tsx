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

describe("financial statement assessment skill", () => {
  it("shows the complete five-dimension method in its required order", () => {
    renderSkillsPage();

    const headings = screen.getAllByRole("heading", { level: 3 }).map((heading) => heading.textContent);
    expect(headings).toEqual([
      "Profitability",
      "Liquidity",
      "Balance sheet and leverage",
      "Cash flow",
      "Efficiency and sector",
    ]);
  });

  it("keeps execution disabled until the backend contract exists", () => {
    renderSkillsPage();

    expect(screen.getByText(/backend connection required/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /run assessment/i })).toBeDisabled();
    expect(screen.getByText(/not yet present in the published api contract/i)).toBeInTheDocument();
  });

  it("makes decision and evidence boundaries explicit", () => {
    renderSkillsPage();

    expect(screen.getByText(/no approval, decline, rating, or credit-limit output/i)).toBeInTheDocument();
    expect(screen.getByText(/missing figures remain not disclosed/i)).toBeInTheDocument();
    expect(screen.getByText(/indicative context is not verified peer evidence/i)).toBeInTheDocument();
  });
});
