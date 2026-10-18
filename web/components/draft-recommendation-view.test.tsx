import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DraftRecommendationView } from "./draft-recommendation-view";
import { SessionProvider, type UserSession } from "./session-provider";

const originalBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
const session: UserSession = {
  token: "local-test-token",
  user: {
    permissions: ["case:read"],
    roles: ["underwriter"],
    subject: "local-underwriter",
    tenant_id: "demo-tenant",
  },
};

const draft = {
  ai_proposed_amount: "80000.00",
  band: "REDUCED" as const,
  case_id: "case-1",
  created_at: "2026-10-11T12:00:00Z",
  created_by: "local-analyst",
  decline_findings: [],
  factors: [{ code: "missing_information" as const, explanation: "Latest aging is absent." }],
  id: "draft-1",
  information_gaps: ["Current receivables aging was not supplied."],
  limitations: ["This draft supports, but does not replace, human underwriting judgment."],
  notice: "Draft recommendation for the underwriter. Not a decision.",
  outcome: "APPROVE" as const,
  policy_version: "1.1",
  reasons: [
    {
      evidence: [
        {
          document_id: null,
          kind: "web" as const,
          location: null,
          quote: "Revenue remained stable during the period.",
          retrieved_at: "2026-10-10T10:00:00Z",
          url: "https://example.com/filing",
        },
      ],
      text: "Stable reported revenue supports continued trade terms.",
    },
  ],
  recommended_amount: "75000.00",
  requested_amount: "100000.00",
  requested_currency: "CAD",
  rule_codes: ["R-04"],
  source: {
    kind: "claude_code_session" as const,
    model: "test-model",
    policy_version: "1.1",
    skill_version: "financial-assessment-1",
  },
  summary: "The evidence supports a reduced draft amount, subject to the stated gaps.",
  test_product: true,
  version: 2,
};

function renderView(initialSession: UserSession | null = session) {
  return render(
    <SessionProvider initialSession={initialSession ?? undefined}>
      <DraftRecommendationView caseId="case-1" draftId="draft-1" />
    </SessionProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  if (originalBaseUrl === undefined) delete process.env.NEXT_PUBLIC_API_BASE_URL;
  else process.env.NEXT_PUBLIC_API_BASE_URL = originalBaseUrl;
});

describe("draft recommendation view", () => {
  it("shows loading before rendering a labelled, traceable non-decision", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000";
    let resolveRequest: (value: Response) => void = () => undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(
        () => new Promise<Response>((resolve) => (resolveRequest = resolve)),
      ),
    );

    renderView();
    expect(screen.getByText(/retrieving the draft recommendation/i)).toBeInTheDocument();

    resolveRequest(new Response(JSON.stringify(draft), { status: 200 }));

    expect(await screen.findByRole("heading", { name: draft.notice })).toBeInTheDocument();
    expect(screen.getByText("Stable reported revenue supports continued trade terms.")).toBeInTheDocument();
    expect(screen.getByText("Current receivables aging was not supplied.")).toBeInTheDocument();
    expect(screen.getByText(/does not replace, human underwriting judgment/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open source/i })).toHaveAttribute(
      "href",
      "https://example.com/filing",
    );
    expect(document.body).not.toHaveTextContent(/\bapprove\b|\bdecline\b/i);
    expect(screen.queryByRole("button", { name: /approve|decline|adopt|reject/i })).not.toBeInTheDocument();
  });

  it("makes empty rationale sections explicit without inventing values", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            ...draft,
            factors: [],
            information_gaps: [],
            limitations: [],
            reasons: [],
            rule_codes: [],
          }),
          { status: 200 },
        ),
      ),
    );

    renderView();

    expect(await screen.findByText(/no reasons or evidence references were recorded/i)).toBeInTheDocument();
    expect(screen.getByText(/no lowering factors were recorded/i)).toBeInTheDocument();
    expect(screen.getByText(/no information gaps were recorded/i)).toBeInTheDocument();
    expect(screen.getByText(/no limitations were recorded/i)).toBeInTheDocument();
    expect(screen.getByText("Not recorded")).toBeInTheDocument();
    expect(screen.queryByText("N/A")).not.toBeInTheDocument();
  });

  it("requires an in-memory session before calling the API", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    renderView(null);

    expect(screen.getByRole("heading", { name: /sign in to view this draft/i })).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([
    [403, "forbidden", "You do not have permission to view this draft.", /you don’t have access/i],
    [404, "not_found", "The draft was not found.", /draft recommendation not found/i],
  ])("shows the safe %s API state", async (status, code, message, heading) => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: { code, correlation_id: "request-1234", message, retryable: false },
          }),
          { headers: { "X-Request-ID": "request-1234" }, status },
        ),
      ),
    );

    renderView();

    expect(await screen.findByRole("heading", { name: heading })).toBeInTheDocument();
    expect(screen.getByText(message)).toBeInTheDocument();
    expect(screen.getByText(/request ID: request-1234/i)).toBeInTheDocument();
  });

  it("shows a safe retryable state for network failure", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000";
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("private stack detail")));

    renderView();

    expect(await screen.findByRole("heading", { name: /could not load draft recommendation/i })).toBeInTheDocument();
    expect(screen.queryByText(/private stack detail/i)).not.toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText(/retrieving/i)).not.toBeInTheDocument());
  });
});
