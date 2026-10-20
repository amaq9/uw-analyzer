import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FinalDecisionTab } from "@/components/case/final-decision-tab";
import { SessionProvider, type UserSession } from "@/components/session-provider";

const session: UserSession = {
  token: "t",
  user: { permissions: ["case:read"], roles: ["underwriter"], subject: "u", tenant_id: "x" },
};
const record = { legal_name: "Maple Leaf Fabrication Ltd.", jurisdiction: "Canada", industry: "Fabrication" } as never;

const draft = {
  id: "d1",
  version: 1,
  outcome: "APPROVE",
  band: "REDUCED",
  requested_amount: "1000000.00",
  requested_currency: "CAD",
  recommended_amount: "750000.00",
  ai_proposed_amount: "750000.00",
  summary: "Equity is CAD 9m.",
  reasons: [{ text: "Liquidity needs attention. Cash less debt is -CAD 1m.", evidence: [{ kind: "document", quote: "q" }] }],
  factors: [],
  information_gaps: ["Gap A", "Gap A"],
  limitations: ["Payment behaviour was not assessed."],
  source: { model: "m", skill_version: "1" },
  policy_version: "1.1",
  created_by: "analyst",
  created_at: "2026-10-12T12:00:00Z",
};
const decision = {
  action: "ADOPT",
  final_outcome: "APPROVE",
  final_amount: "750000.00",
  currency: "CAD",
  reason: null,
  agrees: true,
  decided_by: "underwriter-demo",
  decided_at: "2026-10-18T18:00:00Z",
};

function stub(decisionBody: unknown, status = 200) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      Promise.resolve(
        String(url).endsWith("/decision")
          ? new Response(JSON.stringify(decisionBody), { status })
          : new Response(JSON.stringify([draft]), { status: 200 }),
      ),
    ),
  );
}

function renderTab() {
  render(
    <SessionProvider initialSession={session}>
      <FinalDecisionTab caseId="c1" onChanged={() => undefined} permissions={[]} record={record} token="t" />
    </SessionProvider>,
  );
}

const originalBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

beforeEach(() => {
  process.env.NEXT_PUBLIC_API_BASE_URL = "http://api.test";
});

afterEach(() => {
  vi.unstubAllGlobals();
  if (originalBaseUrl === undefined) delete process.env.NEXT_PUBLIC_API_BASE_URL;
  else process.env.NEXT_PUBLIC_API_BASE_URL = originalBaseUrl;
});

describe("UW Analyzer Decision Summary", () => {
  it("shows only the summary of the recorded decision, with no doubled currency", async () => {
    stub(decision);
    renderTab();
    const page = await screen.findByLabelText("UW Analyzer Decision Summary");
    expect(page.textContent).toContain("Underwriter decision");
    expect(screen.getByText("Approve CAD 750,000")).toBeInTheDocument();
    expect(page.textContent).toContain("Decided by underwriter-demo.");
    expect(screen.getByText("Test product")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /print or save as pdf/i })).toBeInTheDocument();
    expect(screen.queryByLabelText("Final decision report")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /CEO summary|full decision record/i })).not.toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/CAD CAD/);
  });

  it("reads like a page for the chief executive, without the points to settle", async () => {
    const analysis = {
      areas: [
        {
          key: "leverage",
          title: "Balance sheet and leverage",
          status: "OK",
          finding: "Strong",
          trend: "Stable",
          why: "",
          feeds_draft: true,
          metrics: [
            { label: "Debt to equity", current: "0.74x", prior: "0.83x", earlier: "", change: "down", reference: "below 1.0" },
            { label: "Interest cover (EBIT over interest)", current: "11.92x", prior: "9.71x", earlier: "", change: "up", reference: "above 2.5" },
          ],
        },
        {
          key: "profitability",
          title: "Profitability",
          status: "WEAK",
          finding: "Concerning",
          trend: "Stable",
          why: "",
          feeds_draft: true,
          metrics: [{ label: "Revenue", current: "CAD 46.40m", prior: "CAD 46.31m", earlier: "", change: "flat", reference: "" }],
        },
      ],
      red_flags: [
        { text: "Free cash flow not covering dividends and buybacks", state: "TRIGGERED", detail: "After them it is -CAD 369k.", result: "" },
        { text: "Something clear", state: "CLEAR", detail: "Fine.", result: "" },
        { text: "Negative outlook from an agency", state: "TRIGGERED", detail: "Negative outlook: S&P A.", result: "" },
      ],
      notes_review: { findings: [{ title: "Auditor's opinion", state: "NO_CONCERN", summary: "Clean." }], source: "", summary: "", characters: 1 },
      other_checks: [
        { title: "Sanctions list (OFAC SDN)", state: "CLEAR", detail: "" },
        { title: "Court records and other regulators", state: "NOT_SEARCHED", detail: "" },
      ],
      published_ratings: [
        { id: "r1", agency: "SP", grade: "A", change: "DOWNGRADE", outlook: "NEGATIVE", under_review: false, last_action_on: "2026-10-05", source_kind: "OTHER" },
      ],
      executive_brief: {
        headline: "Approve a reduced CAD 750,000, 75% of the CAD 1.00m requested. Balance sheet is sound; profitability is under pressure.",
        sections: [{ heading: "If sales fall", text: "Operating profit reaches zero if revenue falls about 19.3%." }],
        points_to_settle: ["Confirm the agency ratings on the agencies' own websites."],
      },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        Promise.resolve(
          String(url).endsWith("/decision")
            ? new Response(JSON.stringify(decision), { status: 200 })
            : new Response(JSON.stringify([{ ...draft, analysis, factors: [{ code: "f", explanation: "Profitability is weak." }] }]), {
                status: 200,
              }),
        ),
      ),
    );
    renderTab();
    const page = await screen.findByLabelText("UW Analyzer Decision Summary");
    const text = page.textContent ?? "";
    expect(text).toContain("Approve CAD 750,000");
    expect(text).toContain("75% of the CAD 1.00m requested");
    expect(text).toContain("In line with the UW Analyzer recommendation.");
    expect(text).toContain("Balance sheet is sound; profitability is under pressure.");
    expect(text).toContain("Balance sheet and leverage strong: debt to equity 0.74x, interest cover 11.92x");
    expect(text).toContain("Clean (unqualified) audit opinion");
    expect(text).toContain("No match on the U.S. sanctions list");
    expect(text).toContain("Free cash flow not covering dividends and buybacks: After them it is -CAD 369k");
    expect(text).not.toContain("Something clear");
    expect(text).not.toContain("Negative outlook from an agency"); // said once, under the agencies
    expect(text).toContain("S&P A, downgraded, negative outlook");
    expect(text).toContain("(as reported in the press)");
    expect(text).toContain("Operating profit reaches zero if revenue falls about 19.3%.");
    expect(text).toContain("Below the request because: Profitability is weak.");
    expect(text).toContain("Not covered by this review: Court records and other regulators.");
    expect(text).toContain("Profitability: weak");
    expect(text).not.toMatch(/points to settle|Confirm the agency ratings/i);
  });

  it("says no decision has been recorded and offers no report until one is", async () => {
    stub({ error: { code: "not_found", message: "none", correlation_id: "x", retryable: false } }, 404);
    renderTab();
    expect(await screen.findByText("No decision has been recorded yet")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /print/i })).not.toBeInTheDocument();
  });
});
