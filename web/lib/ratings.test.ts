import { describe, expect, it } from "vitest";

import { AGENCY_SITES, isAgencySite } from "@/lib/ratings";

describe("the agencies' own websites are the main sources", () => {
  it("names the three sites the Product Owner chose", () => {
    expect(AGENCY_SITES.SP.label).toBe("www.spglobal.com");
    expect(AGENCY_SITES.MOODYS.label).toBe("ratings.moodys.com");
    expect(AGENCY_SITES.FITCH.label).toBe("www.fitchratings.com");
  });

  it.each([
    ["SP", "https://www.spglobal.com/ratings/en/research/articles/x", true],
    ["SP", "https://ratings.spglobal.com/x", true],
    ["SP", "https://WWW.SPGLOBAL.COM/ratings", true],
    ["MOODYS", "https://ratings.moodys.com/ratings-news/123", true],
    ["MOODYS", "https://www.moodys.com/credit-ratings/Nike-Inc-credit-rating-40400", true],
    ["FITCH", "https://www.fitchratings.com/research/x", true],
    ["FITCH", "https://fitchratings.com/entity/nike", true],
    // Look-alikes and tricks never count.
    ["SP", "https://evil-spglobal.com/ratings", false],
    ["SP", "https://spglobal.com.evil.org/ratings", false],
    ["SP", "https://www.spglobal.com@evil.org/ratings", false],
    ["FITCH", "https://www.fitchrating.com/x", false],
    ["MOODYS", "https://moodys.com.evil.org/x", false],
    // Another agency's site, press, and rubbish are not this agency's site.
    ["MOODYS", "https://www.spglobal.com/ratings", false],
    ["SP", "https://capital.com/en-au/news/nike-falls", false],
    ["SP", "not a web address", false],
    ["SP", "", false],
  ] as const)("%s %s -> %s", (agency, address, expected) => {
    expect(isAgencySite(agency, address)).toBe(expected);
  });
});
