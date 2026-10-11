import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CaseList } from "./case-list";
import { SessionProvider, type UserSession } from "./session-provider";

const originalBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
const readSession: UserSession = {
  token: "local-test-token",
  user: {
    permissions: ["case:read"],
    roles: ["auditor"],
    subject: "case-reader",
    tenant_id: "demo-tenant",
  },
};
const writeSession: UserSession = {
  ...readSession,
  user: { ...readSession.user, permissions: ["case:read", "case:write"], roles: ["underwriter"] },
};

function record(index = 1) {
  return {
    address: null,
    context: null,
    created_at: `2026-10-${String(12 - index).padStart(2, "0")}T12:00:00Z`,
    exposure_amount: null,
    exposure_currency: null,
    id: `00000000-0000-4000-8000-${String(index).padStart(12, "0")}`,
    industry: null,
    information_gaps: [{ description: "Registration number is missing.", field: "registration_number" }],
    jurisdiction: index === 1 ? "Canada" : null,
    legal_name: index === 1 ? "Northstar Components Ltd." : null,
    owner: "case-reader",
    parent_name: null,
    registration_number: null,
    resolved_at: null,
    resolved_by: null,
    resolved_candidate_id: null,
    status: "DRAFT" as const,
    terms: null,
    trading_name: index === 1 ? "Northstar" : `Trading entity ${index}`,
    ubo_name: null,
    updated_at: `2026-10-${String(12 - index).padStart(2, "0")}T13:00:00Z`,
    version: 1,
    website: null,
  };
}

function renderList(session: UserSession | null = writeSession) {
  return render(
    <SessionProvider initialSession={session ?? undefined}>
      <CaseList />
    </SessionProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  if (originalBaseUrl === undefined) delete process.env.NEXT_PUBLIC_API_BASE_URL;
  else process.env.NEXT_PUBLIC_API_BASE_URL = originalBaseUrl;
});

describe("case list", () => {
  it("shows loading, then newest-first case details and write actions", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000";
    let resolveRequest: (response: Response) => void = () => undefined;
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>((resolve) => (resolveRequest = resolve))));

    renderList();
    expect(screen.getByRole("heading", { name: /retrieving cases/i })).toBeInTheDocument();
    resolveRequest(new Response(JSON.stringify([record(1), record(2)]), { status: 200 }));

    expect(await screen.findByText("Northstar Components Ltd.")).toBeInTheDocument();
    expect(screen.getByText("Northstar")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /new case/i })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /edit/i })).toHaveLength(2);
    expect(screen.getByText("Canada")).toBeInTheDocument();
    expect(screen.getAllByText("1").length).toBeGreaterThan(0);
  });

  it("shows a truthful empty state and hides write actions without case:write", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000";
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("[]", { status: 200 })));

    renderList(readSession);

    expect(await screen.findByRole("heading", { name: /no cases yet/i })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /new case|create the first case/i })).not.toBeInTheDocument();
  });

  it("requests the next page with limit and offset", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000";
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(Array.from({ length: 10 }, (_, i) => record(i + 1))), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([record(11)]), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    renderList();
    const next = await screen.findByRole("button", { name: /next/i });
    fireEvent.click(next);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(fetchMock.mock.calls[1][0]).toContain("limit=10&offset=10");
    expect(screen.getByText("Page 2")).toBeInTheDocument();
  });

  it("shows the API's clear forbidden state", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ error: { code: "forbidden", correlation_id: "request-403", message: "Case access is not permitted.", retryable: false } }),
          { headers: { "X-Request-ID": "request-403" }, status: 403 },
        ),
      ),
    );

    renderList();

    expect(await screen.findByRole("heading", { name: /you don’t have access/i })).toBeInTheDocument();
    expect(screen.getByText("Case access is not permitted.")).toBeInTheDocument();
    expect(screen.getByText(/request ID: request-403/i)).toBeInTheDocument();
  });

  it("requires a memory-only session before calling the API", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    renderList(null);
    expect(screen.getByRole("heading", { name: /sign in to view cases/i })).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
