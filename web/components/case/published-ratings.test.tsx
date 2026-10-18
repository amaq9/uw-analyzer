import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AnalysisReportData } from "@/components/case/analysis-report";
import { PublishedRatings } from "@/components/case/published-ratings";
import { SessionProvider, type UserSession } from "@/components/session-provider";

const session: UserSession = {
  token: "t",
  user: { permissions: ["case:read", "draft:import"], roles: ["underwriter"], subject: "u", tenant_id: "x" },
};
const originalBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

const moodys = {
  id: "r1",
  case_id: "c1",
  agency: "MOODYS",
  grade: "Ba1",
  investment_grade: false,
  outlook: "NEGATIVE",
  under_review: true,
  change: "DOWNGRADE",
  last_action_on: "2026-08-01",
  rationale: "Weaker cash generation.",
  source_url: "https://www.moodys.com/research/acme",
  retrieved_at: "2026-10-10T12:00:00Z",
  quote: "Moody's downgraded Acme to Ba1.",
  recorded_by: "underwriter-demo",
  recorded_at: "2026-10-11T12:00:00Z",
  notice: "n",
};

type Calls = { body?: string; method: string; url: string }[];

function stub(rows: unknown[], calls: Calls = []) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      calls.push({ body: init?.body as string | undefined, method: init?.method ?? "GET", url });
      const post = init?.method === "POST";
      return Promise.resolve(new Response(JSON.stringify(post ? moodys : rows), { status: post ? 201 : 200 }));
    }),
  );
  return calls;
}

function show(canRecord = true, analysis?: Partial<AnalysisReportData>) {
  return render(
    <SessionProvider initialSession={session}>
      <PublishedRatings
        analysis={analysis as AnalysisReportData | undefined}
        canRecord={canRecord}
        caseId="c1"
        token="t"
      />
    </SessionProvider>,
  );
}

beforeEach(() => {
  process.env.NEXT_PUBLIC_API_BASE_URL = "http://api.test";
});

afterEach(() => {
  vi.unstubAllGlobals();
  if (originalBaseUrl === undefined) delete process.env.NEXT_PUBLIC_API_BASE_URL;
  else process.env.NEXT_PUBLIC_API_BASE_URL = originalBaseUrl;
});

describe("published credit ratings", () => {
  it("says plainly when no rating is recorded, for each agency, and that it is not our rating", async () => {
    stub([]);
    show();
    expect(await screen.findAllByText("No published rating recorded")).toHaveLength(3);
    expect(screen.getByText(/not this product.s rating/i)).toBeInTheDocument();
    expect(screen.getByText(/do\s+not change the draft recommendation/i)).toBeInTheDocument();
  });

  it("shows a recorded rating in words with its source, and uses no status colour", async () => {
    stub([moodys]);
    const { container } = show();
    const row = (await screen.findByText("Ba1")).closest("tr") as HTMLElement;
    expect(within(row).getByText("Below investment grade")).toBeInTheDocument();
    expect(within(row).getByText("Negative")).toBeInTheDocument();
    expect(within(row).getByText("Under review")).toBeInTheDocument();
    expect(within(row).getByText("Downgrade")).toBeInTheDocument();
    expect(within(row).getByRole("link", { name: "Open source" })).toHaveAttribute("href", moodys.source_url);
    expect(within(row).getByText(/Moody's downgraded Acme to Ba1/)).toBeInTheDocument();
    expect(container.querySelector(".st-chip")).toBeNull();
    expect(screen.getAllByText("No published rating recorded")).toHaveLength(2);
  });

  it("shows how the ratings compare with the financial analysis, and flags a later rating", async () => {
    stub([moodys]);
    show(true, { published_ratings: [], ratings_reconciliation: "The two differ. Look closer." });
    expect(await screen.findByText(/The two differ\. Look closer\./)).toBeInTheDocument();
    expect(screen.getByText(/recorded after this draft was prepared/i)).toBeInTheDocument();
  });

  it("records a rating with its source and the quoted words", async () => {
    const calls = stub([]);
    show();
    await screen.findAllByText("No published rating recorded");
    fireEvent.click(screen.getByText("Record a published rating"));
    const submit = screen.getByRole("button", { name: /record this rating/i });
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/^grade/i), { target: { value: "Baa2" } });
    fireEvent.change(screen.getByLabelText(/^source address/i), { target: { value: "https://example.com/x" } });
    fireEvent.change(screen.getByLabelText(/own words/i), { target: { value: "Affirmed at Baa2." } });
    fireEvent.change(screen.getByLabelText(/^outlook/i), { target: { value: "STABLE" } });
    expect(submit).toBeEnabled();
    fireEvent.click(submit);
    await waitFor(() => expect(calls.some((call) => call.method === "POST")).toBe(true));
    const post = calls.find((call) => call.method === "POST");
    expect(post?.url).toContain("/api/v1/cases/c1/published-ratings");
    const sent = JSON.parse(post?.body ?? "{}");
    expect(sent).toMatchObject({
      agency: "MOODYS",
      grade: "Baa2",
      outlook: "STABLE",
      source_url: "https://example.com/x",
      quote: "Affirmed at Baa2.",
      under_review: false,
    });
    expect(typeof sent.retrieved_at).toBe("string");
  });

  it("offers no form to a role that cannot record", async () => {
    stub([]);
    show(false);
    expect(await screen.findByText(/your role cannot record a published rating/i)).toBeInTheDocument();
    expect(screen.queryByText("Record a published rating")).not.toBeInTheDocument();
  });
});
