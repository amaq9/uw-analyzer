import { describe, expect, it } from "vitest";

import { splitGaps } from "@/lib/gaps";

describe("splitGaps", () => {
  it("keeps real gaps as gaps and moves old 'Figure derived' notes to definitions", () => {
    const out = splitGaps(["Sector outlook was not assessed", "Figure derived: EBITDA is EBIT plus depreciation", "Sector outlook was not assessed"]);
    expect(out.gaps).toEqual(["Sector outlook was not assessed"]);
    expect(out.definitions).toEqual(["EBITDA is EBIT plus depreciation"]);
  });

  it("merges the report's own definitions without repeats", () => {
    const out = splitGaps([], ["EBIT is operating profit.", "EBIT is operating profit."]);
    expect(out.gaps).toEqual([]);
    expect(out.definitions).toEqual(["EBIT is operating profit."]);
  });
});
