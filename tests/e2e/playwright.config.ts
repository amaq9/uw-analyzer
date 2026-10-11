import { defineConfig, devices } from "@playwright/test";
import { fileURLToPath } from "node:url";

export default defineConfig({
  expect: { timeout: 5_000 },
  fullyParallel: false,
  reporter: "list",
  retries: process.env.CI ? 2 : 0,
  testDir: ".",
  testIgnore: "playwright.config.ts",
  use: {
    ...devices["Desktop Chrome"],
    baseURL: "http://127.0.0.1:3000",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "npm run dev -- --hostname 127.0.0.1",
    cwd: fileURLToPath(new URL("../../web", import.meta.url)),
    env: {
      ...process.env,
      NEXT_PUBLIC_API_BASE_URL: "http://127.0.0.1:8000",
    },
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    url: "http://127.0.0.1:3000",
  },
});
