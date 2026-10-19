import { describe, expect, it } from "vitest";

import { groupRepeatChecks } from "@/components/case/evidence-tab";
import type { ClaimRecord } from "@/components/case/types";

type Link = ClaimRecord["links"][number];

function link(id: string, accessed: string, over: Partial<Link["evidence"]> = {}, relation = "SUPPORTS"): Link {
  return {
    id,
    relation,
    evidence: {
      title: "OFAC sanctions list name search for NIKE, Inc.",
      source_id: "ofac",
      origin: "treasury.gov",
      url: null,
      accessed_at: accessed,
      ...over,
    },
  } as unknown as Link;
}

describe("repeat checks of a source on one claim", () => {
  it("keeps the newest check first and folds the earlier ones under it", () => {
    const groups = groupRepeatChecks([
      link("a", "2026-10-11T20:50:38Z"),
      link("b", "2026-10-18T23:37:53Z"),
      link("c", "2026-10-11T20:50:38Z", { title: "OFAC SDN list name search for NIKE, Inc." }),
    ]);
    expect(groups.map((g) => g.map((l) => l.id))).toEqual([["b", "a"], ["c"]]);
  });

  it("never folds a different document, address or relation from the same source together", () => {
    const groups = groupRepeatChecks([
      link("figures", "2026-10-11T00:00:00Z", { source_id: "sec", title: "Annual report data" }),
      link("filing", "2026-10-18T00:00:00Z", { source_id: "sec", title: "Annual report data", url: "https://www.sec.gov/x" }),
      link("against", "2026-10-18T00:00:00Z", { source_id: "sec", title: "Annual report data" }, "CONTRADICTS"),
    ]);
    expect(groups).toHaveLength(3);
  });
});
