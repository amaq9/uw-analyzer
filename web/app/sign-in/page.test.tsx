import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import SignInPage from "./page";

describe("enterprise access screen", () => {
  it("does not imply that identity integration is already active", () => {
    render(<SignInPage />);

    expect(screen.getByRole("button", { name: /enterprise sso/i })).toBeDisabled();
    expect(screen.getByText(/being configured/i)).toBeInTheDocument();
    expect(screen.getByText(/local passwords are not stored/i)).toBeInTheDocument();
  });
});
