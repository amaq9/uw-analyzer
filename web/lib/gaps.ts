/** Drafts made before definitions had their own list carried them in the gaps as "Figure derived: X is Y". */
const LEGACY_DEFINITION = /^Figure derived:\s*/i;

/** Splits missing information (gaps) from notes on how figures were defined (method, not a gap). */
export function splitGaps(gaps: readonly string[], definitions: readonly string[] = []): { gaps: string[]; definitions: string[] } {
  const legacy = gaps.filter((gap) => LEGACY_DEFINITION.test(gap)).map((gap) => gap.replace(LEGACY_DEFINITION, ""));
  return {
    gaps: [...new Set(gaps.filter((gap) => !LEGACY_DEFINITION.test(gap)))],
    definitions: [...new Set([...definitions, ...legacy])],
  };
}
