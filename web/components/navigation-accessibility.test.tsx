import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SessionProvider, type UserSession } from "@/components/session-provider";
import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";

function session(permissions: string[]): UserSession {
  return {
    token: "local-test-token",
    user: {
      permissions,
      roles: ["underwriter"],
      subject: "local-underwriter",
      tenant_id: "demo-tenant",
    },
  };
}

describe("workspace navigation", () => {
  it("provides a visible sign-out action that clears the memory-only session", () => {
    render(
      <SessionProvider initialSession={session(["case:read"])} key="case-reader">
        <Topbar />
      </SessionProvider>,
    );

    expect(screen.getByText("local-underwriter")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));

    expect(screen.queryByRole("button", { name: "Sign out" })).not.toBeInTheDocument();
    expect(screen.getByText("Authorized user")).toBeInTheDocument();
  });

  it("shows protected navigation only when the current user has a matching permission", () => {
    const { rerender } = render(
      <SessionProvider initialSession={session(["case:read"])}>
        <Sidebar />
      </SessionProvider>,
    );

    expect(screen.getByRole("link", { name: "Cases" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Source access" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Audit history" })).not.toBeInTheDocument();

    rerender(
      <SessionProvider initialSession={session(["audit:read"])} key="auditor">
        <Sidebar />
      </SessionProvider>,
    );

    expect(screen.getByRole("link", { name: "Audit history" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Cases" })).not.toBeInTheDocument();
  });

  it("groups the links into Workspace, Analysis and Governance, in order", () => {
    render(
      <SessionProvider initialSession={session(["case:read", "audit:read"])}>
        <Sidebar activePage="agreement" />
      </SessionProvider>,
    );

    const listed = (name: string) =>
      within(screen.getByRole("list", { name })).getAllByRole("link").map((link) => link.textContent);
    expect(listed("Workspace")).toEqual(["Overview", "Cases", "Skills"]);
    expect(listed("Analysis")).toEqual(["UW Analyzer recommendation", "Decision Outcome"]);
    expect(listed("Governance")).toEqual(["Source access", "Audit history"]);
    expect(screen.getByRole("link", { name: "UW Analyzer recommendation" })).toHaveAttribute("href", "/recommendations");
    expect(screen.getByRole("link", { name: "Decision Outcome" })).toHaveAttribute("href", "/agreement");
    expect(screen.getByRole("link", { name: "Decision Outcome" })).toHaveAttribute("aria-current", "page");
  });

  it("leaves out a section, heading and all, when none of its links are allowed", () => {
    render(
      <SessionProvider>
        <Sidebar />
      </SessionProvider>,
    );

    expect(screen.getByRole("list", { name: "Workspace" })).toBeInTheDocument();
    expect(screen.queryByText("Analysis")).not.toBeInTheDocument();
    expect(screen.queryByText("Governance")).not.toBeInTheDocument();
  });
});
