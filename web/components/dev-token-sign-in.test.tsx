import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DevTokenSignIn } from "./dev-token-sign-in";

const originalBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

afterEach(() => {
  vi.unstubAllGlobals();
  if (originalBaseUrl === undefined) {
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
  } else {
    process.env.NEXT_PUBLIC_API_BASE_URL = originalBaseUrl;
  }
});

describe("development token sign-in", () => {
  it("validates the token through /me and shows the returned identity", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000";
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          permissions: ["case:read", "case:write"],
          roles: ["underwriter"],
          subject: "local-underwriter",
          tenant_id: "demo-tenant",
        }),
        { headers: { "Content-Type": "application/json" }, status: 200 },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<DevTokenSignIn />);
    fireEvent.change(screen.getByLabelText(/local development token/i), {
      target: { value: "test-token" },
    });
    fireEvent.click(screen.getByRole("button", { name: /continue to local workspace/i }));

    expect(await screen.findByText(/signed in as local-underwriter/i)).toBeInTheDocument();
    expect(screen.getByText("demo-tenant")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/me",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer test-token" }),
      }),
    );
  });

  it("shows a safe API message and request ID without echoing the token", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: {
              code: "unauthenticated",
              correlation_id: "request-1234",
              message: "The token is invalid or expired.",
              retryable: false,
            },
          }),
          { headers: { "X-Request-ID": "request-1234" }, status: 401 },
        ),
      ),
    );

    render(<DevTokenSignIn />);
    fireEvent.change(screen.getByLabelText(/local development token/i), {
      target: { value: "secret-test-token" },
    });
    fireEvent.click(screen.getByRole("button", { name: /continue to local workspace/i }));

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(screen.getByText(/token is invalid or expired/i)).toBeInTheDocument();
    expect(screen.getByText(/request ID: request-1234/i)).toBeInTheDocument();
    expect(screen.queryByText("secret-test-token")).not.toBeInTheDocument();
  });
});
