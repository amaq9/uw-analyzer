import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CaseForm } from "./case-form";
import { SessionProvider, type UserSession } from "./session-provider";

const { pushMock } = vi.hoisted(() => ({ pushMock: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: pushMock }) }));

const originalBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
const writeSession: UserSession = {
  token: "local-test-token",
  user: {
    permissions: ["case:read", "case:write"],
    roles: ["underwriter"],
    subject: "local-underwriter",
    tenant_id: "demo-tenant",
  },
};

function record(version = 3) {
  return {
    address: null,
    context: "Existing context",
    created_at: "2026-10-10T12:00:00Z",
    exposure_amount: "100000.00",
    exposure_currency: "CAD",
    id: "00000000-0000-4000-8000-000000000001",
    industry: null,
    information_gaps: [],
    jurisdiction: "Canada",
    legal_name: "Northstar Components Ltd.",
    owner: "local-underwriter",
    parent_name: null,
    registration_number: "BC123",
    resolved_at: null,
    resolved_by: null,
    resolved_candidate_id: null,
    status: "DRAFT" as const,
    terms: "Net 30",
    trading_name: "Northstar",
    ubo_name: null,
    updated_at: "2026-10-11T12:00:00Z",
    version,
    website: "https://example.com",
  };
}

function renderForm(mode: "create" | "edit", session: UserSession = writeSession) {
  return render(
    <SessionProvider initialSession={session}>
      {mode === "create" ? <CaseForm mode="create" /> : <CaseForm caseId={record().id} mode="edit" />}
    </SessionProvider>,
  );
}

afterEach(() => {
  pushMock.mockReset();
  vi.unstubAllGlobals();
  if (originalBaseUrl === undefined) delete process.env.NEXT_PUBLIC_API_BASE_URL;
  else process.env.NEXT_PUBLIC_API_BASE_URL = originalBaseUrl;
});

describe("case form", () => {
  it("blocks create and edit controls without case:write", () => {
    renderForm("create", {
      ...writeSession,
      user: { ...writeSession.user, permissions: ["case:read"] },
    });

    expect(screen.getByRole("heading", { name: /you don’t have access/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /create case/i })).not.toBeInTheDocument();
  });

  it("validates the paired exact exposure fields, website, and required name", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    renderForm("create");

    fireEvent.change(screen.getByLabelText("Exposure amount"), { target: { value: "12.345" } });
    fireEvent.change(screen.getByLabelText("Website"), { target: { value: "example.com" } });
    fireEvent.click(screen.getByRole("button", { name: /create case/i }));

    expect(await screen.findAllByText(/enter a legal name or a trading name/i)).toHaveLength(2);
    expect(screen.getByText(/exact non-negative amount/i)).toBeInTheDocument();
    expect(screen.getByText(/currency must be entered together/i)).toBeInTheDocument();
    expect(screen.getByText(/must start with http/i)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("creates a case with the exact amount string and paired currency", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000";
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(record(1)), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);
    renderForm("create");

    fireEvent.change(screen.getByLabelText("Legal name"), { target: { value: "Northstar Components Ltd." } });
    fireEvent.change(screen.getByLabelText("Exposure amount"), { target: { value: "1250000.50" } });
    fireEvent.change(screen.getByLabelText("Exposure currency"), { target: { value: "cad" } });
    fireEvent.click(screen.getByRole("button", { name: /create case/i }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toMatchObject({
      exposure_amount: "1250000.50",
      exposure_currency: "CAD",
      legal_name: "Northstar Components Ltd.",
    });
    expect(pushMock).toHaveBeenCalledWith(`/cases/${record(1).id}`);
  });

  it("places server field errors next to their fields", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: {
              code: "validation_error",
              correlation_id: "request-422",
              field_errors: [{ field: "website", message: "Website is not accepted." }],
              message: "Check the highlighted fields.",
              retryable: false,
            },
          }),
          { status: 422 },
        ),
      ),
    );
    renderForm("create");
    fireEvent.change(screen.getByLabelText("Trading name"), { target: { value: "Northstar" } });
    fireEvent.click(screen.getByRole("button", { name: /create case/i }));

    expect(await screen.findByText("Website is not accepted.")).toBeInTheDocument();
    expect(screen.getByLabelText("Website")).toHaveAttribute("aria-invalid", "true");
  });

  it("sends expected_version and null to clear an optional edit field", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000";
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(record()), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...record(4), context: null }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    renderForm("edit");

    expect(await screen.findByDisplayValue("Existing context")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Case context"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const init = fetchMock.mock.calls[1][1] as RequestInit;
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(String(init.body))).toMatchObject({ context: null, expected_version: 3 });
    expect(JSON.parse(String(init.body))).not.toHaveProperty("status");
  });

  it("shows a normal not-found state when the case cannot be loaded", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: {
              code: "not_found",
              correlation_id: "request-404",
              message: "Case not found.",
              retryable: false,
            },
          }),
          { status: 404 },
        ),
      ),
    );
    renderForm("edit");

    expect(await screen.findByRole("heading", { name: /case not found/i })).toBeInTheDocument();
    expect(screen.getByText("Case not found.")).toBeInTheDocument();
  });

  it("locks resolved identity fields and explains the required reopen", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            ...record(),
            resolved_at: "2026-10-11T13:00:00Z",
            resolved_by: "local-underwriter",
            status: "ENTITY_RESOLVED",
          }),
          { status: 200 },
        ),
      ),
    );
    renderForm("edit");

    expect(await screen.findByText(/reopen it before changing/i)).toBeInTheDocument();
    expect(screen.getByLabelText("Legal name")).toBeDisabled();
    expect(screen.getByLabelText("Registration number")).toBeDisabled();
    expect(screen.getByLabelText("Jurisdiction")).toBeDisabled();
    expect(screen.getByLabelText("Trading name")).toBeEnabled();
  });

  it("shows the server conflict, reloads, and lets the user redo the edit", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000";
    const latest = { ...record(4), context: "Updated elsewhere" };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(record()), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ error: { code: "conflict", correlation_id: "request-409", message: "The case was changed by another user.", retryable: false } }),
          { status: 409 },
        ),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify(latest), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    renderForm("edit");

    await screen.findByDisplayValue("Existing context");
    fireEvent.click(screen.getByRole("button", { name: /save changes/i }));

    expect(await screen.findByText("The case was changed by another user.")).toBeInTheDocument();
    expect(screen.getByText(/latest case was reloaded/i)).toBeInTheDocument();
    expect(screen.getByDisplayValue("Updated elsewhere")).toBeInTheDocument();
  });
});
