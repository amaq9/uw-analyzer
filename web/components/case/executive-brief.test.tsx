import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ExecutiveBriefCard, type ExecutiveBriefData } from "@/components/case/executive-brief";

const brief: ExecutiveBriefData = {
  headline: "Approve a reduced USD 3.75m, 75% of the USD 5.00m requested. Profitability is under pressure.",
  sections: [
    { heading: "Recommendation", text: "Approve a reduced USD 3.75m. The reduction comes from: liquidity (-15%)." },
    { heading: "Financial position in numbers", text: "Revenue USD 46.40bn; net margin 6.7%; interest cover 11.92x." },
    { heading: "What the rating agencies say", text: "Moody's A2 (negative outlook); S&P A (downgraded, negative outlook)." },
    { heading: "Screening and external checks", text: "OFAC sanctions list: no exact or possible match." },
  ],
  points_to_settle: ["Confirm the agency ratings on the agencies' own websites.", "Ask what is behind the longer cash cycle."],
};

describe("executive summary for the decision-maker", () => {
  it("leads with the recommendation, gives each part under its heading and lists what to settle first", () => {
    render(<ExecutiveBriefCard brief={brief} currency="USD" />);
    const card = screen.getByLabelText("Executive summary for the decision-maker");
    expect(within(card).getByText(/Approve a reduced USD 3.75m, 75% of the USD 5.00m requested/)).toBeInTheDocument();
    for (const heading of ["Recommendation", "Financial position in numbers", "What the rating agencies say", "Screening and external checks"]) {
      expect(within(card).getByText(heading)).toBeInTheDocument();
    }
    expect(within(card).getByText(/interest cover 11.92x/)).toBeInTheDocument();
    expect(within(card).getByRole("heading", { name: "Points to settle first" })).toBeInTheDocument();
    expect(within(card).getAllByRole("listitem")).toHaveLength(2);
    expect(within(card).getByText(/recommendation only/i)).toBeInTheDocument();
  });

  it("shows no list of points when there are none, and never doubles the currency", () => {
    render(<ExecutiveBriefCard brief={{ ...brief, points_to_settle: [] }} currency="USD" />);
    expect(screen.queryByRole("heading", { name: "Points to settle first" })).not.toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/USD USD/);
  });
});
