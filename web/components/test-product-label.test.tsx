import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TestProductLabel } from "./test-product-label";

describe("test product label", () => {
  it("keeps the test-product status visible without decision wording", () => {
    render(<TestProductLabel />);

    expect(screen.getByLabelText(/test product environment/i)).toHaveTextContent("Test product");
    expect(screen.queryByText(/score|rating|approve|decline/i)).not.toBeInTheDocument();
  });
});
