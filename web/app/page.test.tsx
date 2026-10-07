import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Home from "./page";

describe("workspace foundation", () => {
  it("keeps the human-underwriter boundary explicit", () => {
    render(<Home />);

    expect(
      screen.getByRole("heading", { name: /evidence you can follow/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/the underwriter decides/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /approve|decline/i })).not.toBeInTheDocument();
  });

  it("surfaces the entity ambiguity stop-control", () => {
    render(<Home />);

    expect(screen.getByText("Entity resolution")).toBeInTheDocument();
    expect(screen.getByText("Required gate")).toBeInTheDocument();
    expect(screen.getByText(/substantive research stops/i)).toBeInTheDocument();
  });

  it("separates source access from claim verification", () => {
    render(<Home />);

    expect(screen.getByText(/access and verification remain separate/i)).toBeInTheDocument();
  });
});
