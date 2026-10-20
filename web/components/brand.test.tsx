import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Brand } from "@/components/brand";

describe("brand", () => {
  it("shows the crosshair mark beside the name and links home", () => {
    const { container } = render(<Brand />);
    const link = screen.getByRole("link", { name: "UW Analyzer home" });
    expect(link).toHaveAttribute("href", "/");
    const mark = container.querySelector("svg.brand-mark");
    expect(mark).toHaveAttribute("aria-hidden", "true");
    expect(mark?.querySelectorAll("line")).toHaveLength(2);
    expect(mark?.querySelector(".brand-mark-ring")).not.toBeNull();
    expect(mark?.querySelector(".brand-mark-dot")).not.toBeNull();
    expect(screen.getByText("UW Analyzer")).toBeInTheDocument();
    expect(screen.getByText("Evidence-led underwriting")).toBeInTheDocument();
  });
});
