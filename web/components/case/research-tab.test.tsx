import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ResearchTab } from "@/components/case/research-tab";
import { SessionProvider, type UserSession } from "@/components/session-provider";

const session: UserSession = {
  token: "t",
  user: { permissions: ["case:read", "research:run"], roles: ["underwriter"], subject: "u", tenant_id: "x" },
};

const originalBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

beforeEach(() => {
  process.env.NEXT_PUBLIC_API_BASE_URL = "http://api.test";
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response("[]", { status: 200 }))));
});

afterEach(() => {
  vi.unstubAllGlobals();
  if (originalBaseUrl === undefined) delete process.env.NEXT_PUBLIC_API_BASE_URL;
  else process.env.NEXT_PUBLIC_API_BASE_URL = originalBaseUrl;
});

function renderTab(status: string) {
  return render(
    <SessionProvider initialSession={session}>
      <ResearchTab caseId="c1" onChanged={() => undefined} permissions={session.user.permissions} status={status} token="t" />
    </SessionProvider>,
  );
}

const BLOCKED = "Research is blocked until the legal entity has been chosen on the Entity tab.";

describe("the research tab and the entity gate", () => {
  it("says research is blocked, and disables planning, only while the entity is not resolved", async () => {
    renderTab("ENTITY_AMBIGUOUS");
    expect(await screen.findByText(BLOCKED)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create research plan" })).toBeDisabled();
  });

  it("does not claim research is blocked once the entity is resolved", async () => {
    renderTab("ENTITY_RESOLVED");
    await waitFor(() => expect(screen.getByRole("button", { name: "Create research plan" })).toBeEnabled());
    expect(screen.queryByText(BLOCKED)).not.toBeInTheDocument();
  });
});
