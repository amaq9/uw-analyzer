import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sources(path);
    return /\.tsx$/.test(name) && !/\.test\.tsx$/.test(name) ? [path] : [];
  });
}

describe("form controls keep a clean accessible name", () => {
  it("gives every dropdown an explicit name, so a label that wraps it is not read out with its options", () => {
    const offenders: string[] = [];
    for (const path of [...sources("components"), ...sources("app")]) {
      const text = readFileSync(path, "utf8");
      for (const match of text.matchAll(/<select\b[^>]*>/g)) {
        if (!match[0].includes("aria-label")) offenders.push(`${path}: ${match[0].slice(0, 70)}`);
      }
    }
    expect(offenders).toEqual([]);
  });

  it("never names a form field after the token or secret it holds (it would be sent in the URL by a plain submit)", () => {
    const offenders: string[] = [];
    for (const path of [...sources("components"), ...sources("app")]) {
      const text = readFileSync(path, "utf8");
      for (const match of text.matchAll(/<(input|textarea)\b[^>]*\bname="[^"]*(token|secret|password)[^"]*"[^>]*>/gi)) {
        offenders.push(`${path}: ${match[0].slice(0, 70)}`);
      }
    }
    expect(offenders).toEqual([]);
  });
});
