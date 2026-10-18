import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

import { describe, expect, it } from "vitest";

// Line endings are not part of the contract: git on Windows checks files out with CRLF.
const lf = (text: string) => text.replaceAll("\r\n", "\n");

describe("generated API types", () => {
  it("match the current OpenAPI contract", () => {
    const temporaryDirectory = mkdtempSync(join(tmpdir(), "uw-analyzer-api-types-"));
    const temporarySchema = join(temporaryDirectory, "schema.d.ts");

    try {
      execFileSync(
        process.execPath,
        [
          resolve("node_modules/openapi-typescript/bin/cli.js"),
          resolve("../docs/api/openapi.json"),
          "--output",
          temporarySchema,
        ],
        { stdio: "pipe" },
      );

      expect(lf(readFileSync(resolve("lib/api/schema.d.ts"), "utf8"))).toBe(
        lf(readFileSync(temporarySchema, "utf8")),
      );
    } finally {
      rmSync(temporaryDirectory, { force: true, recursive: true });
    }
  });
});
