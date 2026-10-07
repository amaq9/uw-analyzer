import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import SkillsPage from "./page";

describe("financial statement assessment skill", () => {
  it("shows the complete five-area method in its required order", () => {
    render(<SkillsPage />);

    const headings = screen.getAllByRole("heading", { level: 3 }).map((heading) => heading.textContent);
    expect(headings).toEqual([
      "Balance sheet strength",
      "Liquidity",
      "Gearing",
      "Receivables aging",
      "Cash flow generation",
    ]);
  });

  it("keeps execution disabled until the backend contract exists", () => {
    render(<SkillsPage />);

    expect(screen.getByText(/backend connection required/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /run assessment/i })).toBeDisabled();
    expect(screen.getByText(/not yet present in the published api contract/i)).toBeInTheDocument();
  });

  it("makes decision and evidence boundaries explicit", () => {
    render(<SkillsPage />);

    expect(screen.getByText(/no approval, decline, rating, or credit-limit output/i)).toBeInTheDocument();
    expect(screen.getByText(/missing figures remain not disclosed/i)).toBeInTheDocument();
    expect(screen.getByText(/indicative context is not verified peer evidence/i)).toBeInTheDocument();
  });
});
