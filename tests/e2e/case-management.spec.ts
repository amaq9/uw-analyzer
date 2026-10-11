import { expect, test, type Page, type Route } from "@playwright/test";

const apiOrigin = "http://127.0.0.1:8000";
const browserOrigin = "http://127.0.0.1:3000";

type CaseRecord = ReturnType<typeof makeCase>;

function makeCase(overrides: Record<string, unknown> = {}) {
  return {
    address: null,
    context: "Initial context",
    created_at: "2026-10-11T12:00:00Z",
    exposure_amount: "100000.00",
    exposure_currency: "CAD",
    id: "00000000-0000-4000-8000-000000000001",
    industry: "Manufacturing",
    information_gaps: [
      { description: "Ultimate beneficial owner is missing.", field: "ubo_name" },
    ],
    jurisdiction: "Canada",
    legal_name: "Northstar Components Ltd.",
    owner: "local-underwriter",
    parent_name: null,
    registration_number: "BC123",
    resolved_at: null,
    resolved_by: null,
    resolved_candidate_id: null,
    status: "DRAFT",
    terms: "Net 30",
    trading_name: "Northstar",
    ubo_name: null,
    updated_at: "2026-10-11T13:00:00Z",
    version: 1,
    website: "https://example.com",
    ...overrides,
  };
}

function fulfillJson(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    body: JSON.stringify(body),
    headers: {
      "Access-Control-Allow-Headers": "Authorization, Content-Type",
      "Access-Control-Allow-Methods": "GET, POST, PATCH, OPTIONS",
      "Access-Control-Allow-Origin": browserOrigin,
      "Content-Type": "application/json",
      "X-Request-ID": "e2e-request",
    },
    status,
  });
}

async function mockApi(page: Page, initialCases: CaseRecord[]) {
  const state = { cases: [...initialCases], lastPatch: undefined as Record<string, unknown> | undefined };

  await page.route(`${apiOrigin}/api/v1/**`, async (route) => {
    const request = route.request();
    const url = new URL(request.url());

    if (request.method() === "OPTIONS") {
      await route.fulfill({
        headers: {
          "Access-Control-Allow-Headers": "Authorization, Content-Type",
          "Access-Control-Allow-Methods": "GET, POST, PATCH, OPTIONS",
          "Access-Control-Allow-Origin": browserOrigin,
        },
        status: 204,
      });
      return;
    }

    if (url.pathname === "/api/v1/me") {
      await fulfillJson(route, {
        permissions: ["case:read", "case:write"],
        roles: ["underwriter"],
        subject: "local-underwriter",
        tenant_id: "demo-tenant",
      });
      return;
    }

    if (url.pathname === "/api/v1/cases" && request.method() === "GET") {
      const offset = Number(url.searchParams.get("offset") ?? 0);
      const limit = Number(url.searchParams.get("limit") ?? 10);
      await fulfillJson(route, state.cases.slice(offset, offset + limit));
      return;
    }

    if (url.pathname === "/api/v1/cases" && request.method() === "POST") {
      const input = request.postDataJSON() as Record<string, unknown>;
      const created = makeCase({
        ...input,
        id: "00000000-0000-4000-8000-000000000003",
        information_gaps: [],
        legal_name: input.legal_name ?? null,
        trading_name: input.trading_name ?? null,
      });
      state.cases.unshift(created);
      await fulfillJson(route, created, 201);
      return;
    }

    const caseId = url.pathname.match(/^\/api\/v1\/cases\/([^/]+)$/)?.[1];
    if (caseId) {
      const index = state.cases.findIndex((record) => record.id === caseId);
      if (index < 0) {
        await fulfillJson(route, { error: { code: "not_found", correlation_id: "e2e-404", message: "Case not found.", retryable: false } }, 404);
        return;
      }

      if (request.method() === "GET") {
        await fulfillJson(route, state.cases[index]);
        return;
      }

      if (request.method() === "PATCH") {
        const input = request.postDataJSON() as Record<string, unknown>;
        state.lastPatch = input;
        state.cases[index] = makeCase({ ...state.cases[index], ...input, version: Number(state.cases[index].version) + 1 });
        await fulfillJson(route, state.cases[index]);
        return;
      }
    }

    await fulfillJson(route, { error: { code: "not_found", correlation_id: "e2e-404", message: "Not found.", retryable: false } }, 404);
  });

  return state;
}

async function signInAndOpenCases(page: Page) {
  await page.goto("/sign-in");
  await page.getByLabel("Local development token").fill("e2e-local-token");
  await page.getByRole("button", { name: "Continue to local workspace" }).click();
  await expect(page.getByRole("heading", { name: /signed in as local-underwriter/i })).toBeVisible();
  await page.getByRole("link", { name: "Continue to workspace" }).click();
  await page.getByRole("link", { name: "Cases" }).click();
  await expect(page).toHaveURL(/\/cases$/);
}

test("lists cases newest first and pages through the API", async ({ page }) => {
  const cases = Array.from({ length: 11 }, (_, index) =>
    makeCase({
      id: `00000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`,
      legal_name: `Entity ${index + 1}`,
      updated_at: `2026-10-${String(11 - index).padStart(2, "0")}T13:00:00Z`,
    }),
  );
  await mockApi(page, cases);
  await signInAndOpenCases(page);

  const rows = page.locator("tbody tr");
  await expect(rows.first()).toContainText("Entity 1");
  await expect(rows).toHaveCount(10);
  await page.getByRole("button", { exact: true, name: "Next" }).click();
  await expect(page.getByText("Page 2")).toBeVisible();
  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toContainText("Entity 11");
});

test("creates a case with an exact amount and paired currency", async ({ page }) => {
  await mockApi(page, []);
  await signInAndOpenCases(page);
  await page.getByRole("link", { name: "Create the first case" }).click();

  await page.getByLabel("Trading name").fill("Maple Distribution");
  await page.getByLabel("Exposure amount").fill("1250000.50");
  await page.getByLabel("Exposure currency").fill("cad");
  await page.getByLabel("Website").fill("https://example.com");
  await page.getByRole("button", { name: "Create case" }).click();

  await expect(page).toHaveURL(/\/cases$/);
  await expect(page.getByText("Maple Distribution")).toBeVisible();
  await expect(page.getByRole("link", { name: "Edit" })).toBeVisible();
});

test("edits with expected_version and sends null when a field is cleared", async ({ page }) => {
  const state = await mockApi(page, [makeCase()]);
  await signInAndOpenCases(page);
  await page.getByRole("link", { name: "Edit" }).click();

  await expect(page.getByLabel("Case context")).toHaveValue("Initial context");
  await page.getByLabel("Requested terms").fill("");
  await page.getByLabel("Case context").fill("Updated by the underwriter");
  await page.getByRole("button", { name: "Save changes" }).click();

  await expect(page).toHaveURL(/\/cases$/);
  expect(state.lastPatch).toMatchObject({
    context: "Updated by the underwriter",
    expected_version: 1,
    terms: null,
  });
  expect(state.lastPatch).not.toHaveProperty("status");
  expect(state.lastPatch).not.toHaveProperty("owner");
});
