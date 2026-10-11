import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AnalysisPanel } from "@/components/case/analysis-panel";
import { SessionProvider } from "@/components/session-provider";

const originalBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

const result = {
  status: "DRAFT_PREPARED",
  message: "A draft recommendation was prepared for the underwriter. It is not a decision.",
  sections: [
    { key: "balance_sheet", title: "Balance sheet strength", assessment: "STRONG", trend: "Stable", why: "Equity is USD 14.87bn.", flags: [] },
    { key: "cash_flow", title: "Cash flow generation", assessment: "NEEDS_ATTENTION", trend: "Weakening", why: "Operating cash flow fell.", flags: ["Operating cash flow below net income"] },
  ],
  consolidated_assessment: "SATISFACTORY",
  consolidated_why: "The core sections are not weak together.",
  periods_reviewed: ["2026-05-31", "2025-05-31"],
  requested_amount: "5000000.00",
  proposed_amount: "4000000.00",
  currency: "USD",
  factors: [{ code: "missing_information", explanation: "Information is missing: the sector outlook was not assessed." }],
  information_gaps: ["Sector-level outlook was not assessed"],
  evidence_created: 1,
  claims_created: 7,
  draft: null,
  review_item_id: null,
};

beforeEach(() => {
  process.env.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000";
});

afterEach(() => {
  vi.unstubAllGlobals();
  if (originalBaseUrl === undefined) delete process.env.NEXT_PUBLIC_API_BASE_URL;
  else process.env.NEXT_PUBLIC_API_BASE_URL = originalBaseUrl;
});

describe("analysis panel", () => {
  it("runs the analysis and shows each section in words with reasons, never a score", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(new Response(JSON.stringify(result), { status: 201 })));
    vi.stubGlobal("fetch", fetchMock);
    render(
      <SessionProvider>
        <AnalysisPanel base="/api/v1/cases/c1" canRun onDone={() => undefined} token="t" />
      </SessionProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: /analyse the research/i }));
    expect(await screen.findByText("Balance sheet strength")).toBeInTheDocument();
    expect(screen.getByText("Needs attention")).toBeInTheDocument();
    expect(screen.getByText("Weakening")).toBeInTheDocument();
    expect(screen.getByText(/they are not scores or ratings/i)).toBeInTheDocument();
    expect(screen.getByText(/USD 4.00m/)).toBeInTheDocument();
    expect(screen.getByText(/Consolidated financial findings/)).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain("/api/v1/cases/c1/analysis");
    expect(init.method).toBe("POST");
    expect(document.body).not.toHaveTextContent(/\/10|score of|rating of/i);
  });

  it("explains why it cannot run, in plain words", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({ error: { code: "conflict", message: "No finished research run with a successful source call was found. Plan and start research first.", correlation_id: "abc", retryable: false } }),
            { status: 409 },
          ),
        ),
      ),
    );
    render(
      <SessionProvider>
        <AnalysisPanel base="/api/v1/cases/c1" canRun onDone={() => undefined} token="t" />
      </SessionProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: /analyse the research/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/plan and start research first/i);
  });

  it("is not offered to roles that cannot run it", () => {
    render(
      <SessionProvider>
        <AnalysisPanel base="/api/v1/cases/c1" canRun={false} onDone={() => undefined} token="t" />
      </SessionProvider>,
    );
    expect(screen.queryByRole("button", { name: /analyse the research/i })).not.toBeInTheDocument();
    expect(screen.getByText(/cannot run the analysis/i)).toBeInTheDocument();
  });
});
