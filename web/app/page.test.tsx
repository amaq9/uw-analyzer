import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SessionProvider } from "@/components/session-provider";

import Home from "./page";

function renderHome() {
  return render(
    <SessionProvider>
      <Home />
    </SessionProvider>,
  );
}

describe("workspace foundation", () => {
  it("keeps the human-underwriter boundary explicit", () => {
    renderHome();

    expect(
      screen.getByRole("heading", { name: /evidence you can follow/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/the underwriter decides/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /approve|decline/i })).not.toBeInTheDocument();
  });

  it("surfaces the entity ambiguity stop-control", () => {
    renderHome();

    expect(screen.getByText("Entity resolution")).toBeInTheDocument();
    expect(screen.getByText("Required gate")).toBeInTheDocument();
    expect(screen.getByText(/substantive research stops/i)).toBeInTheDocument();
  });

  it("separates source access from claim verification", () => {
    renderHome();

    expect(screen.getByText(/access and verification remain separate/i)).toBeInTheDocument();
  });
});
