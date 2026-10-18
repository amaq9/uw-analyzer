import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DecisionForm } from "@/components/case/decision-form";
import { RecommendationTab } from "@/components/case/recommendation-tab";
import type { DraftRecord } from "@/components/case/types";
import { SessionProvider, type UserSession } from "@/components/session-provider";

const session: UserSession = {
  token: "t",
  user: { permissions: ["case:read", "decision:record", "draft:import"], roles: ["underwriter"], subject: "u", tenant_id: "x" },
};
const originalBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

beforeEach(() => {
  process.env.NEXT_PUBLIC_API_BASE_URL = "http://api.test";
});

afterEach(() => {
  vi.unstubAllGlobals();
  if (originalBaseUrl === undefined) delete process.env.NEXT_PUBLIC_API_BASE_URL;
  else process.env.NEXT_PUBLIC_API_BASE_URL = originalBaseUrl;
});

function renderTab() {
  return render(
    <SessionProvider initialSession={session}>
      <RecommendationTab
        caseId="c1"
        onChanged={() => undefined}
        permissions={session.user.permissions}
        token="t"
      />
    </SessionProvider>,
  );
}

describe("the Draft recommendation tab while it loads", () => {
  it("shows a loading note, never a false 'no draft yet', until the drafts have arrived", async () => {
    let release: (value: Response) => void = () => undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        String(url).endsWith("/draft-recommendations")
          ? new Promise<Response>((resolve) => {
              release = resolve;
            })
          : Promise.resolve(new Response("[]", { status: 200 })),
      ),
    );
    renderTab();
    expect(screen.getByText("Loading the drafts of this case…")).toBeInTheDocument();
    expect(screen.queryByText("No draft has been prepared yet")).not.toBeInTheDocument();
    expect(screen.queryByText("Available once a draft has been prepared.")).not.toBeInTheDocument();
    release(new Response("[]", { status: 200 }));
    expect(await screen.findByText("No draft has been prepared yet")).toBeInTheDocument();
    expect(screen.getByText("Available once a draft has been prepared.")).toBeInTheDocument();
    expect(screen.queryByText("Loading the drafts of this case…")).not.toBeInTheDocument();
  });

  it("says plainly when the drafts could not be loaded, and does not claim there are none", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify({ error: { code: "x", message: "The server is busy.", correlation_id: "c", retryable: true } }), {
            status: 503,
          }),
        ),
      ),
    );
    renderTab();
    expect(await screen.findByText(/The drafts could not be loaded/)).toBeInTheDocument();
    expect(screen.queryByText("No draft has been prepared yet")).not.toBeInTheDocument();
  });
});

describe("the decision form tells the truth about what it will record", () => {
  const draft = {
    id: "d1",
    version: 6,
    outcome: "APPROVE",
    band: "REDUCED",
    requested_amount: "5000000.00",
    requested_currency: "USD",
    recommended_amount: "3750000.00",
  } as unknown as DraftRecord;

  function renderForm() {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response("{}", { status: 201 }))));
    render(
      <SessionProvider initialSession={session}>
        <DecisionForm base="/api/v1/cases/c1/draft-recommendations" draft={draft} onDone={() => undefined} token="t" />
      </SessionProvider>,
    );
  }

  it("previews exactly what adopting records, and asks for nothing more", () => {
    renderForm();
    expect(screen.getByText("You will record: Approve a reduced amount: USD 3.75m.")).toBeInTheDocument();
    expect(screen.queryByText(/Still needed/)).not.toBeInTheDocument();
  });

  it("never previews an amount above the request, and says what is still needed", () => {
    renderForm();
    fireEvent.click(screen.getByLabelText(/change it/i));
    expect(screen.getByText(/Still needed: an amount above zero and not above the amount requested and your reason\./)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/^amount/i), { target: { value: "6000000" } });
    expect(screen.getByText(/That amount cannot be recorded: it is above the amount requested\./)).toBeInTheDocument();
    expect(screen.queryByText(/You will record: Approve USD 6\.00m/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /record my decision/i })).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/^amount/i), { target: { value: "4000000" } });
    expect(screen.getByText("You will record: Approve USD 4.00m.")).toBeInTheDocument();
    expect(screen.getByText(/Still needed: your reason\./)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/reason/i), { target: { value: "My own view of the sector." } });
    expect(screen.queryByText(/Still needed/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /record my decision/i })).toBeEnabled();
  });

  it("needs a written reason to reject, and says so", () => {
    renderForm();
    fireEvent.click(screen.getByLabelText(/reject it/i));
    expect(screen.getByText(/Still needed: your reason\./)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /record my decision/i })).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/reason/i), { target: { value: "Wrong entity." } });
    expect(screen.getByRole("button", { name: /record my decision/i })).toBeEnabled();
  });

  it("records nothing until the button is pressed, and then records exactly what was previewed", async () => {
    const calls: { body?: string; url: string }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        calls.push({ body: init?.body as string | undefined, url });
        return Promise.resolve(new Response("{}", { status: 201 }));
      }),
    );
    render(
      <SessionProvider initialSession={session}>
        <DecisionForm base="/api/v1/cases/c1/draft-recommendations" draft={draft} onDone={() => undefined} token="t" />
      </SessionProvider>,
    );
    fireEvent.click(screen.getByLabelText(/change it/i));
    fireEvent.change(screen.getByLabelText(/^amount/i), { target: { value: "4000000" } });
    fireEvent.change(screen.getByLabelText(/reason/i), { target: { value: "My own view." } });
    expect(calls).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: /record my decision/i }));
    await waitFor(() => expect(calls).toHaveLength(1));
    expect(JSON.parse(calls[0].body ?? "{}")).toEqual({
      action: "CHANGE",
      reason: "My own view.",
      final_outcome: "APPROVE",
      final_amount: "4000000",
    });
  });
});
