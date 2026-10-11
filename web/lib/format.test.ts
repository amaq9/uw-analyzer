import { describe, expect, it } from "vitest";

import { money, shorten } from "@/lib/format";

describe("display helpers", () => {
  it("shows currency with every amount and converts large amounts to billions or millions", () => {
    expect(money("5000000", "USD")).toBe("USD 5.00m");
    expect(money("38410000000", "USD")).toBe("USD 38.41bn");
    expect(money("-369000000", "USD")).toBe("-USD 369.00m");
    expect(money(null, "USD")).toBe("Not provided");
  });

  it("rewrites analyst figures in millions with the case currency", () => {
    expect(shorten("assets 24,603m over liabilities 12,547m and 499m of goodwill", "USD")).toBe(
      "assets USD 24.60bn over liabilities USD 12.55bn and USD 499m of goodwill",
    );
    expect(shorten("net cash of 1,085m", "CAD")).toBe("net cash of CAD 1.09bn");
    expect(shorten("1.96x and 38.7% of assets", "USD")).toBe("1.96x and 38.7% of assets");
  });
});
