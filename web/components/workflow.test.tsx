import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Workflow } from "@/components/workflow";

describe("core workflow", () => {
  it("shows five numbered stages in order, with entity resolution marked as the required gate", () => {
    const { container } = render(<Workflow />);

    const stages = within(screen.getByRole("list")).getAllByRole("listitem");
    expect(stages).toHaveLength(5);
    expect(stages.map((stage) => stage.querySelector(".track-node")?.textContent)).toEqual(["01", "02", "03", "04", "05"]);
    expect(screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent)).toEqual([
      "Stage 01: Case intake",
      "Stage 02: Entity resolution",
      "Stage 03: Controlled research",
      "Stage 04: Evidence review",
      "Stage 05: Human review",
    ]);

    const gates = container.querySelectorAll(".track-stage.is-gate");
    expect(gates).toHaveLength(1);
    expect(within(gates[0] as HTMLElement).getByText("Required gate")).toBeInTheDocument();
    expect(gates[0]?.querySelector(".track-lock")).not.toBeNull();
    expect(screen.getByText("5 controlled stages")).toBeInTheDocument();
    expect(screen.getByText(/substantive research stops until a human resolves the ambiguity/)).toBeInTheDocument();
  });
});
