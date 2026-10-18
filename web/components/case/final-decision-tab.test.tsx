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

describe("final decision report", () => {
  it("shows the recorded decision on one page, with no doubled currency and each gap once", async () => {
    stub(decision);
    renderTab();
    expect(await screen.findByLabelText("Final decision report")).toBeInTheDocument();
    expect(screen.getByText("Approve CAD 750,000")).toBeInTheDocument();
    expect(screen.getByText("Underwriter decision")).toBeInTheDocument();
    expect(screen.getByText("Test product")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /print or save as pdf/i })).toBeInTheDocument();
    expect(screen.getAllByText("Gap A")).toHaveLength(1);
    expect(document.body.textContent).not.toMatch(/CAD CAD/);
  });

  it("says no decision has been recorded and offers no report until one is", async () => {
    stub({ error: { code: "not_found", message: "none", correlation_id: "x", retryable: false } }, 404);
    renderTab();
    expect(await screen.findByText("No decision has been recorded yet")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /print/i })).not.toBeInTheDocument();
  });
});
