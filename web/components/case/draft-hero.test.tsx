import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DecisionForm, DecisionSummary } from "@/components/case/decision-form";
import { AnalysisFindings, DraftBasis, DraftHero } from "@/components/case/draft-hero";
import type { DecisionRecord, DraftRecord } from "@/components/case/types";
import { SessionProvider, type UserSession } from "@/components/session-provider";

const session: UserSession = {
  token: "t",
  user: { permissions: ["decision:record"], roles: ["underwriter"], subject: "u", tenant_id: "x" },
};

const draft = {
  id: "d1",
  version: 2,
  outcome: "APPROVE",
  band: "REDUCED",
  requested_amount: "1000000.00",
  requested_currency: "USD",
  recommended_amount: "600000.00",
  ai_proposed_amount: "640000.00",
  rule_codes: ["REDUCED_ROUNDED_DOWN"],
  summary: "Strong liquidity, weak sector outlook.",
  reasons: [
    {
      text: "Liquidity is adequate.",
      evidence: [{ kind: "web", url: "https://example.com/a", quote: "Current ratio 1.8", retrieved_at: "2026-10-10T10:00:00Z" }],
    },
  ],
  factors: [{ code: "sector_outlook", explanation: "Sector outlook is soft." }],
  information_gaps: ["No aging report."],
  limitations: ["Payment behaviour was not assessed."],
  source: { kind: "analyzer_v1", model: "m", skill_version: "1", policy_version: "1.1" },
  policy_version: "1.1",
  created_by: "analyst",
  created_at: "2026-10-11T12:00:00Z",
} as unknown as DraftRecord;

describe("draft recommendation design", () => {
  it("labels the draft as not a decision and as a test product, with the amount against the request", () => {
    render(<DraftHero draft={draft} />);
    expect(screen.getByText("Draft recommendation for the underwriter. Not a decision.")).toBeInTheDocument();
    expect(screen.getByText("Test product")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Approve a reduced amount" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /60 percent of the amount requested/i })).toBeInTheDocument();
  });

  it("states a decline in words with no amount and no meter", () => {
    render(<DraftHero draft={{ ...draft, outcome: "DECLINE", band: "DECLINE", recommended_amount: null } as DraftRecord} />);
    expect(screen.getByRole("heading", { name: "Decline" })).toBeInTheDocument();
    expect(screen.getByText(/no amount is recommended/i)).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("shows reasons with their sources, gaps and the versions recorded", () => {
    render(
      <>
        <AnalysisFindings draft={draft} />
        <DraftBasis draft={draft} />
      </>,
    );
    expect(screen.getAllByText("Liquidity is adequate.").length).toBeGreaterThan(0);
    expect(screen.getByText(/Sector outlook is soft\./)).toBeInTheDocument();
    expect(screen.getByText("Weak sector outlook.")).toBeInTheDocument(); // a readable name, not the code
    expect(screen.getByText(/Current ratio 1.8/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open source" })).toHaveAttribute("href", "https://example.com/a");
    expect(screen.getByText("No aging report.")).toBeInTheDocument();
    expect(screen.getByText("Policy version")).toBeInTheDocument();
  });

  it("shows a repeated information gap once, with no duplicate-key error", () => {
    const errors: unknown[][] = [];
    const spy = vi.spyOn(console, "error").mockImplementation((...args) => void errors.push(args));
    const gap = "Figure derived: ebitda is EBIT plus depreciation and amortisation";
    render(<DraftBasis draft={{ ...draft, information_gaps: [gap, gap] } as DraftRecord} />);
    expect(screen.getAllByText(gap)).toHaveLength(1); // a repeated gap is shown once
    spy.mockRestore();
    expect(errors).toEqual([]);
  });

  it("blocks a changed amount above the amount requested", () => {
    render(
      <SessionProvider initialSession={session}>
        <DecisionForm base="/api/v1/cases/c/draft-recommendations" draft={draft} onDone={() => undefined} token="t" />
      </SessionProvider>,
    );
    fireEvent.click(screen.getByLabelText(/change it/i));
    fireEvent.change(screen.getByLabelText(/^amount/i), { target: { value: "2000000" } });
    expect(screen.getByText(/that is above the amount requested/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /record my decision/i })).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/^amount/i), { target: { value: "700000" } });
    expect(screen.getByText(/You will record: Approve/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/reason/i), { target: { value: "Own view of the sector." } });
    expect(screen.getByRole("button", { name: /record my decision/i })).toBeEnabled();
  });

  it("shows the draft and the human decision side by side, and says whether they match", () => {
    const decision = {
      action: "CHANGE",
      final_outcome: "DECLINE",
      final_amount: null,
      currency: "USD",
      reason: "Weak outlook.",
      agrees: false,
      decided_by: "underwriter-demo",
      decided_at: "2026-10-12T09:00:00Z",
    } as unknown as DecisionRecord;
    render(<DecisionSummary decision={decision} draft={draft} />);
    expect(screen.getByText("The draft said")).toBeInTheDocument();
    expect(screen.getByText("Your decision")).toBeInTheDocument();
    expect(screen.getByText("Your decision differs from the draft.")).toBeInTheDocument();
    expect(screen.getByText(/Weak outlook\./)).toBeInTheDocument();
  });
});
