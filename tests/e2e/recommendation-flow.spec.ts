import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * The recommendation journey in a real browser: Step 1 (research and analysis), Step 2 (draft
 * recommendation), Step 3 (your decision), published ratings, and the one-page final decision
 * report. The API is mocked at the network layer; the browser, the layout and the print styles are real.
 */

const apiOrigin = "http://127.0.0.1:8000";
const browserOrigin = "http://127.0.0.1:3000";
const CASE_ID = "7cfadcf9-bc9c-4c37-ab74-9784507768cb";
const DRAFT_ID = "11111111-1111-4111-8111-111111111111";

const metric = (label: string, current: string, prior: string, earlier: string, change: string, reference = "") => ({
  label,
  current,
  prior,
  earlier,
  change,
  reference,
});

const area = (key: string, title: string, status: string, finding: string, feeds = true, flags: string[] = []) => ({
  key,
  title,
  status,
  finding,
  trend: "Stable",
  why: `${title} reads from the figures. Cash less debt is -USD 1m.`,
  flags,
  metrics: [metric("Current ratio", "1.96x", "2.21x", "2.40x", "down", "1.5 to 2.0")],
  feeds_draft: feeds,
  summary: `${title} is rated ${finding} because its weakest measure is below the reference. This lowers the UW Analyzer's proposed amount by 5% of the amount requested.`,
});

const analysis = {
  basis: {
    statements: "SEC XBRL company facts",
    periods: ["2026-05-31", "2025-05-31", "2024-05-31"],
    currency: "USD",
    units: "Figures shown in millions of USD unless stated",
    audit_note: "Audit status is not stated.",
    method: "Analyst framework: profitability, liquidity, balance sheet and leverage, cash flow, efficiency and sector",
  },
  executive_summary:
    "Consolidated financial findings: weak. The four core dimensions (profitability, liquidity, balance sheet and leverage, cash flow): 1 OK, 3 weak, 0 distressed.",
  areas: [
    area("profitability", "Profitability", "WEAK", "Concerning"),
    area("liquidity", "Liquidity", "WEAK", "Concerning", true, ["Current ratio is lower than the year before"]),
    area("leverage", "Balance sheet and leverage", "OK", "Strong"),
    area("cash_flow", "Cash flow", "WEAK", "Concerning"),
    area("efficiency", "Efficiency and sector", "NOT_ASSESSED", "Not assessed", false),
  ],
  consolidated_status: "WEAK",
  consolidated_finding: "Concerning",
  consolidated_why: "The four core dimensions (profitability, liquidity, balance sheet and leverage, cash flow): 1 OK, 3 weak, 0 distressed.",
  red_flags: [
    { text: "Cash from operations below net income, or negative", state: "TRIGGERED", detail: "Cash from operations USD 2.87bn against net income USD 3.11bn.", result: "Below threshold" },
    { text: "Negative shareholders' equity", state: "CLEAR", detail: "Equity is USD 14.87bn.", result: "Condition not met" },
    { text: "Debt to equity above 2.5", state: "CLEAR", detail: "Debt to equity is 0.74x.", result: "Not above threshold" },
    { text: "Largest customers above 50% of revenue", state: "NOT_ASSESSABLE", detail: "Customer concentration is not in the figures.", result: "Not assessable" },
  ],
  debt_service: [metric("Cash from operations over current liabilities", "0.23x", "0.35x", "0.70x", "down")],
  debt_service_notes: ["The debt maturity ladder is not in the figures."],
  stress: [
    { scenario: "As reported", earnings: "USD 3.85bn", interest_cover: "11.92x", cash_from_operations: "USD 2.87bn" },
    { scenario: "Revenue down 10%, cost of sales falls with sales", earnings: "USD 1.86bn", interest_cover: "5.76x", cash_from_operations: "USD 1.28bn" },
    { scenario: "Revenue down 10%, no cost saving at all (extreme)", earnings: "-USD 790m", interest_cover: "-2.45x", cash_from_operations: "-USD 980m" },
  ],
  stress_note: "Illustration only, not a forecast. Main rows: the cost of sales falls with sales. The last row is the extreme.",
  definitions: ["Net debt is financial debt plus lease liabilities, less cash and short-term investments."],
  cash_cycle: {
    periods: ["2026-05-31", "2025-05-31", "2024-05-31"],
    summary: "The company collects from customers in 46.7 days (was 37.2 days). Cash is therefore tied up for 100.4 days.",
    notes: [],
    status: "WEAK",
    finding: "Concerning",
    trend: "Weakening",
    flags: ["Change in the cash conversion cycle: +8.0 days"],
    standing: "The cash conversion cycle is rated Concerning (shown as Weak) because it is judged by its weakest measure. What to do: Ask for the receivables ageing. This is context only: it does not change the recommended amount.",
    rows: [
      { key: "dso", label: "Days sales outstanding (DSO)", current: "46.7 days", prior: "37.2 days", earlier: "31.5 days", movement: "Longer by 9.5 days (slower collection)", direction: "worse" },
      { key: "dio", label: "Days inventory outstanding (DIO)", current: "103.4 days", prior: "103.1 days", earlier: "96.4 days", movement: "Longer by 0.3 days (slower stock turnover)", direction: "worse" },
      { key: "dpo", label: "Days payables outstanding (DPO)", current: "49.6 days", prior: "47.9 days", earlier: "36.5 days", movement: "Longer by 1.7 days (paying suppliers later)", direction: "better" },
      { key: "ccc", label: "Cash conversion cycle (CCC = DSO + DIO - DPO)", current: "100.4 days", prior: "92.4 days", earlier: "91.3 days", movement: "Longer by 8.0 days (more cash tied up)", direction: "worse" },
    ],
  },
  executive_brief: {
    headline: "Approve a reduced USD 3.75m, 75% of the USD 5.00m requested. Balance sheet and leverage is sound; profitability, liquidity and cash flow are under pressure.",
    sections: [
      { heading: "Recommendation", text: "Approve a reduced USD 3.75m, 75% of the USD 5.00m requested." },
      { heading: "Financial position in numbers", text: "Revenue USD 46.40bn (up 0.2% on the year before); net margin 6.7%; interest cover 11.92x." },
      { heading: "What the rating agencies say", text: "No published agency rating is recorded for this company." },
    ],
    points_to_settle: ["Cash from operations below net income, or negative: Cash from operations USD 2.87bn against net income USD 3.11bn."],
  },
  notes_review: {
    source: "NIKE 10-K for the year ended 2026-05-31: notes and auditor's report",
    url: "https://www.sec.gov/Archives/edgar/data/320187/000032018726000088/nke.htm",
    filed: "2026-07-15",
    sha256: "a".repeat(64),
    characters: 400000,
    summary: "No going-concern warning, covenant breach, auditor qualification or material weakness was stated in the filing text that was read.",
    findings: [
      { topic: "COVENANTS", title: "Loan covenants", state: "NO_CONCERN", summary: "The filing states that the company complied with its covenants.", quotes: [{ text: "We were in compliance with all covenants.", where: null }] },
    ],
  },
  key_concerns: ["Cash from operations below net income, or negative: Cash from operations USD 2.87bn against net income USD 3.11bn."],
  published_ratings: [],
  ratings_reconciliation: "No published rating is recorded, so there is nothing to compare with the financial analysis.",
  strengths: ["Leverage: strong."],
  weaknesses: ["Liquidity: concerning."],
  watch: ["Debt maturities are not in the figures."],
  gaps: ["Sector-level outlook was not assessed."],
  other_checks: [{ title: "Sector outlook", state: "NOT_ASSESSED", detail: "Not assessed." }],
  analyzer_version: "2",
};

const draft = {
  id: DRAFT_ID,
  case_id: CASE_ID,
  version: 5,
  outcome: "APPROVE",
  band: "REDUCED",
  requested_amount: "5000000.00",
  requested_currency: "USD",
  recommended_amount: "3750000.00",
  ai_proposed_amount: "3750000.00",
  rule_codes: [],
  summary: "Consolidated financial findings: weak. Proposed amount USD 3.75m of USD 5m requested.",
  reasons: [
    {
      text: "Liquidity: concerning. Current ratio 1.96x.",
      evidence: [{ kind: "web", url: "https://www.sec.gov/cgi-bin/browse-edgar?CIK=320187", retrieved_at: "2026-10-11T20:29:54Z", quote: "Liquidity for the year ended May 31, 2026" }],
    },
  ],
  decline_findings: [],
  factors: [{ code: "acceptable_not_strong", explanation: "Not strong enough to support the whole amount: liquidity." }],
  information_gaps: ["Sector-level outlook was not assessed."],
  limitations: ["Payment behaviour was not assessed (data not used in this product)."],
  analysis,
  source: { kind: "analyzer_v1", model: "rules engine (no AI model)", skill_version: "analyzer v2", policy_version: "1.1" },
  policy_version: "1.1",
  notice: "UW Analyzer recommendation for the underwriter. Not a decision.",
  test_product: true,
  created_by: "underwriter-demo",
  created_at: "2026-10-18T19:50:36Z",
};

const nike = {
  id: CASE_ID,
  legal_name: "NIKE, Inc.",
  trading_name: null,
  registration_number: null,
  jurisdiction: "United States",
  industry: "Footwear",
  parent_name: null,
  website: null,
  exposure_amount: "5000000.00",
  exposure_currency: "USD",
  terms: null,
  owner: "underwriter-demo",
  status: "ENTITY_RESOLVED",
  information_gaps: [],
  updated_at: "2026-10-11T20:00:00Z",
  created_at: "2026-10-11T20:00:00Z",
  version: 1,
};

type State = {
  decision: Record<string, unknown> | null;
  decisionPosts: Record<string, unknown>[];
  ratings: Record<string, unknown>[];
  ratingPosts: Record<string, unknown>[];
  unsafeUrls: string[];
};

function json(route: Route, body: unknown, status = 200) {
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

const notFound = { error: { code: "not_found", correlation_id: "e2e-404", message: "Not found.", retryable: false } };

async function mockApi(page: Page, options: { permissions?: string[] } = {}): Promise<State> {
  const state: State = { decision: null, decisionPosts: [], ratings: [], ratingPosts: [], unsafeUrls: [] };
  const permissions = options.permissions ?? ["case:read", "case:write", "draft:import", "decision:record"];
  page.on("request", (request) => {
    if (/development-token|e2e-local-token/.test(request.url().replace(apiOrigin, "")) || /[?&](token|code)=/.test(request.url())) {
      state.unsafeUrls.push(request.url());
    }
  });

  await page.route(`${apiOrigin}/api/v1/**`, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
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
    if (path === "/api/v1/me") return json(route, { permissions, roles: ["underwriter"], subject: "underwriter-demo", tenant_id: "demo-tenant" });
    if (path === "/api/v1/cases") return json(route, [nike]);
    if (path === `/api/v1/cases/${CASE_ID}`) return json(route, nike);
    const base = `/api/v1/cases/${CASE_ID}`;
    if (path === `${base}/draft-recommendations`) return json(route, [draft]);
    if (path === `${base}/draft-recommendations/${DRAFT_ID}/decision`) {
      if (request.method() === "POST") {
        const body = request.postDataJSON() as Record<string, unknown>;
        state.decisionPosts.push(body);
        state.decision = {
          id: "22222222-2222-4222-8222-222222222222",
          case_id: CASE_ID,
          draft_id: DRAFT_ID,
          action: body.action,
          final_outcome: body.final_outcome ?? (body.action === "ADOPT" ? "APPROVE" : null),
          final_amount: body.final_amount ?? (body.action === "ADOPT" ? "3750000.00" : null),
          currency: "USD",
          reason: body.reason ?? null,
          agrees: body.action === "ADOPT",
          decided_by: "underwriter-demo",
          decided_at: "2026-10-18T20:10:00Z",
          notice: "Underwriter decision, recorded by a named person.",
          test_product: true,
        };
        return json(route, state.decision, 201);
      }
      return state.decision ? json(route, state.decision) : json(route, notFound, 404);
    }
    if (path === `${base}/published-ratings`) {
      if (request.method() === "POST") {
        const body = request.postDataJSON() as Record<string, unknown>;
        state.ratingPosts.push(body);
        const record = {
          id: `r${state.ratings.length + 1}`,
          case_id: CASE_ID,
          investment_grade: true,
          recorded_by: "underwriter-demo",
          recorded_at: "2026-10-18T20:00:00Z",
          rationale: null,
          last_action_on: null,
          notice: "n",
          ...body,
        };
        state.ratings.push(record);
        return json(route, record, 201);
      }
      return json(route, state.ratings);
    }
    return json(route, request.method() === "GET" ? [] : notFound, request.method() === "GET" ? 200 : 404);
  });
  return state;
}

async function signIn(page: Page) {
  await page.goto("/sign-in");
  await page.getByLabel("Local development token").fill("e2e-local-token");
  await page.getByRole("button", { name: "Continue to local workspace" }).click();
  await expect(page.getByRole("heading", { name: /signed in as underwriter-demo/i })).toBeVisible();
  await page.getByRole("link", { name: "Continue to workspace" }).click();
}

async function openDraft(page: Page) {
  await page.getByRole("navigation", { name: "Primary navigation" }).getByRole("link", { name: "UW Analyzer recommendations" }).click();
  await page.getByRole("link", { name: "Open the recommendation" }).click();
  await expect(page.getByRole("heading", { name: /Step 3 · Your decision/ })).toBeVisible();
}

test.describe("the recommendation journey", () => {
  test("signing in never puts the token in the address bar, even when clicked straight away", async ({ page }) => {
    const state = await mockApi(page);
    await page.goto("/sign-in");
    const button = page.getByRole("button", { name: "Continue to local workspace" });
    await page.getByLabel("Local development token").fill("e2e-local-token");
    await button.click(); // Playwright waits until the button is enabled, as a person's click would
    await expect(page.getByRole("heading", { name: /signed in as underwriter-demo/i })).toBeVisible();
    expect(page.url()).not.toContain("development-token");
    expect(page.url()).not.toContain("e2e-local-token");
    expect(state.unsafeUrls).toEqual([]);
  });

  test("lists the draft waiting for a decision and opens it on the right tab, named in the browser tab", async ({ page }) => {
    await mockApi(page);
    await signIn(page);
    await page.getByRole("navigation", { name: "Primary navigation" }).getByRole("link", { name: "UW Analyzer recommendations" }).click();
    await expect(page).toHaveTitle("UW Analyzer recommendations · UW Analyzer");
    await expect(page.getByText("1 recommendation is waiting for your decision.")).toBeVisible();
    await expect(page.getByRole("row", { name: /NIKE, Inc\./ })).toContainText("Waiting for your decision");
    await expect(page.getByRole("row", { name: /NIKE, Inc\./ })).toContainText("Approve a reduced amount: USD 3.75m");
    await page.getByRole("link", { name: "Open the recommendation" }).click();
    await expect(page).toHaveURL(/tab=recommendation/);
    await expect(page).toHaveTitle("NIKE, Inc. · UW Analyzer recommendation · UW Analyzer");
  });

  test("reads in order: Step 1, then Step 2, then Step 3, with a step bar that stays in view", async ({ page }) => {
    await mockApi(page);
    await signIn(page);
    await openDraft(page);
    const steps = await page.getByRole("heading", { name: /^Step \d · / }).allTextContents();
    expect(steps).toEqual(["Step 1 · Research and analysis", "Step 2 · UW Analyzer recommendation", "Step 3 · Your decision"]);
    const bar = page.getByRole("list", { name: "Progress" });
    await page.getByRole("heading", { name: /Step 3 · Your decision/ }).scrollIntoViewIfNeeded();
    await expect(bar).toBeInViewport(); // sticky: it follows the reader
    await bar.getByRole("link", { name: /Your decision/ }).click();
    await expect(page).toHaveURL(/#rec-step-3$/);
    await bar.getByRole("link", { name: /Research and analysis/ }).click();
    await expect(page.getByRole("heading", { name: /Step 1 · Research and analysis/ })).toBeInViewport();
  });

  test("Step 1 never shows a colour without its word, and says it is not a score", async ({ page }) => {
    await mockApi(page);
    await signIn(page);
    await openDraft(page);
    const chips = page.locator(".st-chip");
    expect(await chips.count()).toBeGreaterThan(5);
    for (const text of await chips.allTextContents()) expect(text).toMatch(/(OK|Weak|Distressed|Not assessed)$/);
    await expect(page.getByText(/not a score or rating of the company/i)).toBeVisible();
    await expect(page.getByLabel("Status of each financial area")).toContainText("Consolidated financial findings");
    // Colour belongs to Step 1 only: nothing in Steps 2 and 3 uses a status chip.
    expect(await page.locator("#rec-step-2 ~ .rec-hero .st-chip, .rec-decide .st-chip, .rec-hero .st-chip").count()).toBe(0);
  });

  test("explains each area in a paragraph, shows the cash cycle, and leads Step 2 with an executive summary", async ({ page }) => {
    await mockApi(page);
    await signIn(page);
    await openDraft(page);
    const titles = await page.locator(".ar-area h3").allTextContents();
    expect(titles.slice(0, 3)).toEqual(["Profitability", "Liquidity", "Balance sheet and leverage"]); // profitability first
    await expect(page.getByText("Why this standing").first()).toBeVisible();
    const cycle = page.getByLabel("Cash conversion cycle");
    await expect(cycle.getByText("46.7 days").first()).toBeVisible();
    await expect(cycle.locator(".st-chip")).toContainText("Weak"); // rated like the other financial areas
    await expect(cycle.getByText(/What to do: Ask for the receivables ageing/)).toBeVisible();
    await expect(cycle.getByText(/Longer by 9.5 days \(slower collection\)/)).toBeVisible();
    const brief = page.getByLabel("Executive summary for the decision-maker");
    await expect(brief.getByText(/Approve a reduced USD 3.75m, 75% of the USD 5.00m requested/).first()).toBeVisible();
    await expect(brief.getByRole("heading", { name: "Points to settle first" })).toBeVisible();
    await expect(brief.getByText("Financial position in numbers")).toBeVisible();
  });

  test("shows the prompts that need a look first and keeps the rest one click away", async ({ page }) => {
    await mockApi(page);
    await signIn(page);
    await openDraft(page);
    const section = page.locator("section.ws-card", { has: page.getByRole("heading", { name: /prompts for the underwriter/ }) });
    await expect(section.getByRole("cell", { name: /Cash from operations below net income/ })).toBeVisible();
    await expect(section.getByRole("cell", { name: "Negative shareholders' equity" })).toBeHidden();
    await section.getByText(/Show the other 3 prompts/).click();
    await expect(section.getByRole("cell", { name: "Negative shareholders' equity" })).toBeVisible();
  });

  test("words each check by its result and colours it: red past the line, green not", async ({ page }) => {
    await mockApi(page);
    await signIn(page);
    await openDraft(page);
    const section = page.locator("section.ws-card", { has: page.getByRole("heading", { name: /prompts for the underwriter/ }) });
    await section.getByText(/Show the other 3 prompts/).click();
    const red = section.getByText("Below threshold", { exact: true });
    const green = section.getByText("Not above threshold", { exact: true });
    await expect(red).toBeVisible();
    await expect(green).toBeVisible();
    const colour = (locator: typeof red) => locator.evaluate((el) => getComputedStyle(el).color);
    expect(await colour(red)).not.toEqual(await colour(green));
    await expect(section.getByText("Not assessable", { exact: true })).toBeVisible();
    await expect(section.getByText("Clear", { exact: true })).toHaveCount(0); // the old wording is gone
  });

  test("shows what the filing's notes say in its own words, and the definitions apart from the gaps", async ({ page }) => {
    await mockApi(page);
    await signIn(page);
    await openDraft(page);
    const notes = page.getByLabel("Notes and auditor's report");
    await expect(notes.getByText("We were in compliance with all covenants.", { exact: false })).toBeVisible();
    await expect(notes.getByRole("link", { name: "Open the filing" })).toHaveAttribute("href", /sec\.gov/);
    const defined = page.getByLabel("How the figures were defined");
    await expect(defined.getByText(/Net debt is financial debt plus lease liabilities/)).toBeVisible();
    await expect(page.locator(".ar-view").getByText("Sector-level outlook was not assessed.")).toBeVisible();
  });

  test("the stress table shows the realistic case and the extreme case apart, with the assumption stated", async ({ page }) => {
    await mockApi(page);
    await signIn(page);
    await openDraft(page);
    await expect(page.getByText("Revenue down 10%, cost of sales falls with sales")).toBeVisible();
    await expect(page.getByText("Revenue down 10%, no cost saving at all (extreme)")).toBeVisible();
    await expect(page.getByText(/The last row is the extreme/)).toBeVisible();
  });

  test("records a published rating with its source and shows it in words, without colour", async ({ page }) => {
    const state = await mockApi(page);
    await signIn(page);
    await openDraft(page);
    const block = page.locator("section.ws-card", { has: page.getByRole("heading", { name: "Published credit ratings" }) });
    await expect(block.getByText("No published rating recorded")).toHaveCount(3);
    await block.getByText("Record a published rating").click();
    await block.getByLabel(/^Grade/).fill("A");
    await block.getByLabel("Agency", { exact: true }).selectOption("SP");
    await block.getByLabel("Outlook", { exact: true }).selectOption("NEGATIVE");
    await expect(block.getByRole("link", { name: /S&P \(www\.spglobal\.com\)/ })).toBeVisible(); // the main sources are named
    await expect(block.getByRole("link", { name: /Moody's \(ratings\.moodys\.com\)/ })).toBeVisible();
    await expect(block.getByRole("link", { name: /Fitch \(www\.fitchratings\.com\)/ })).toBeVisible();
    await block.getByLabel(/Source address/).fill("https://example.com/sp-nike");
    await expect(block.getByText(/This address is not on www\.spglobal\.com, the main source for S&P/)).toBeVisible();
    await block.getByLabel(/own words/).fill("S&P lowered the rating to A with a negative outlook.");
    await block.getByRole("button", { name: "Record this rating" }).click();
    await expect(block.getByRole("cell", { name: /^A\s/ }).first()).toBeVisible();
    await expect(block.getByText(/Secondary source \(press or another site\)\. Confirm it on www\.spglobal\.com\./)).toBeVisible();
    await expect(block.getByText("No published rating recorded")).toHaveCount(2);
    expect(state.ratingPosts).toHaveLength(1);
    expect(state.ratingPosts[0]).toMatchObject({ agency: "SP", grade: "A", outlook: "NEGATIVE", source_url: "https://example.com/sp-nike" });
    expect(typeof state.ratingPosts[0].retrieved_at).toBe("string");
    await expect(block.locator(".st-chip")).toHaveCount(0);
  });

  test("the decision form refuses what it should, previews only what it will record, and records once", async ({ page }) => {
    const state = await mockApi(page);
    await signIn(page);
    await openDraft(page);
    const form = page.locator("section.rec-decide");
    const record = form.getByRole("button", { name: /Record my decision/ });
    await expect(form.getByText("You will record: Approve a reduced amount: USD 3.75m.")).toBeVisible();
    await form.getByLabel(/change it/i).check();
    await expect(record).toBeDisabled();
    await expect(form.getByText(/Still needed: an amount .* and your reason\./)).toBeVisible();
    await form.getByLabel(/^Amount/).fill("6000000");
    await expect(form.getByText("That amount cannot be recorded: it is above the amount requested.")).toBeVisible();
    await expect(form.getByText(/You will record: Approve USD 6\.00m/)).toHaveCount(0);
    await expect(record).toBeDisabled();
    await form.getByLabel(/^Amount/).fill("4000000");
    await form.getByLabel(/Reason/).fill("My own view of the sector.");
    await expect(form.getByText("You will record: Approve USD 4.00m.")).toBeVisible();
    expect(state.decisionPosts).toHaveLength(0); // nothing is decided until the button is pressed
    await record.click();
    await expect(page.getByRole("heading", { name: "Changed the UW Analyzer recommendation" })).toBeVisible();
    expect(state.decisionPosts).toEqual([
      { action: "CHANGE", reason: "My own view of the sector.", final_outcome: "APPROVE", final_amount: "4000000" },
    ]);
    await expect(page.getByText("Your decision differs from the UW Analyzer recommendation.")).toBeVisible();
    await expect(page.getByRole("button", { name: /Record my decision/ })).toHaveCount(0); // cannot be recorded twice
  });

  test("a reject needs a written reason", async ({ page }) => {
    const state = await mockApi(page);
    await signIn(page);
    await openDraft(page);
    const form = page.locator("section.rec-decide");
    await form.getByLabel(/reject it/i).check();
    await expect(form.getByRole("button", { name: /Record my decision/ })).toBeDisabled();
    await form.getByLabel(/Reason/).fill("Wrong entity.");
    await expect(form.getByRole("button", { name: /Record my decision/ })).toBeEnabled();
    expect(state.decisionPosts).toHaveLength(0);
  });

  test("the final decision tab is empty before a decision and a one-page decision summary after it", async ({ page }) => {
    await mockApi(page);
    await page.addInitScript(() => {
      (window as unknown as { __printed: number }).__printed = 0;
      window.print = () => {
        (window as unknown as { __printed: number }).__printed += 1;
      };
    });
    await signIn(page);
    await openDraft(page);
    await page.getByRole("button", { name: "Final decision" }).click();
    await expect(page.getByText("No decision has been recorded yet")).toBeVisible();
    await expect(page.getByRole("button", { name: /Print or save as PDF/ })).toHaveCount(0);

    await page.getByRole("button", { name: "UW Analyzer recommendation" }).click();
    await page.locator("section.rec-decide").getByRole("button", { name: /Record my decision/ }).click();
    await expect(page.getByRole("heading", { name: "Adopted the UW Analyzer recommendation as written" })).toBeVisible();
    await page.getByRole("button", { name: "Open the Final decision tab" }).click();
    const report = page.getByLabel("UW Analyzer Decision Summary");
    await expect(report).toContainText("Approve USD 3.75m");
    const decision = report.getByLabel("Decision", { exact: true });
    await expect(decision).toContainText("Underwriter decision");
    await expect(decision).toContainText("In line with the UW Analyzer recommendation.");
    await expect(report).not.toContainText("Points to settle first");
    await expect(report).toContainText("Test product");
    await expect(report).toContainText("not communicated to any customer");
    await expect(page).toHaveTitle("NIKE, Inc. · Final decision · UW Analyzer");
    await page.getByRole("button", { name: /Print or save as PDF/ }).click();
    expect(await page.evaluate(() => (window as unknown as { __printed: number }).__printed)).toBe(1);
  });

  test("printing shows the report alone: no sidebar, tabs or buttons", async ({ page }) => {
    await mockApi(page);
    await signIn(page);
    await openDraft(page);
    await page.locator("section.rec-decide").getByRole("button", { name: /Record my decision/ }).click();
    await page.getByRole("button", { name: "Open the Final decision tab" }).click();
    await expect(page.getByLabel("UW Analyzer Decision Summary")).toBeVisible();
    await page.emulateMedia({ media: "print" });
    await expect(page.getByLabel("UW Analyzer Decision Summary")).toBeVisible();
    await expect(page.locator(".sidebar")).toBeHidden();
    await expect(page.locator(".topbar")).toBeHidden();
    await expect(page.getByRole("navigation", { name: "Case sections" })).toBeHidden();
    await expect(page.getByRole("button", { name: /Print or save as PDF/ })).toBeHidden();
  });

  test("works from the keyboard alone", async ({ page }) => {
    await mockApi(page);
    await signIn(page);
    await openDraft(page);
    await page.getByRole("button", { name: "Overview" }).focus();
    let focused = "";
    for (let i = 0; i < 12 && focused !== "Final decision"; i += 1) {
      await page.keyboard.press("Tab");
      focused = (await page.evaluate(() => document.activeElement?.textContent ?? "")).trim();
    }
    expect(focused).toBe("Final decision");
    await page.keyboard.press("Enter");
    await expect(page.getByText("No decision has been recorded yet")).toBeVisible();
    // The decision form can be completed with the keyboard too.
    await page.getByRole("button", { name: "UW Analyzer recommendation" }).focus();
    await page.keyboard.press("Enter");
    const adopt = page.getByLabel(/adopt the UW Analyzer recommendation as written/i);
    await adopt.focus();
    await expect(adopt).toBeFocused();
    await page.keyboard.press("ArrowDown");
    await expect(page.getByLabel(/change it/i)).toBeChecked();
  });

  test("every control on the page has a name, and headings do not skip levels", async ({ page }) => {
    await mockApi(page);
    await signIn(page);
    await openDraft(page);
    await page.locator("details.pr-form summary").click();
    const problems = await page.evaluate(() => {
      const name = (el: Element) =>
        (el.getAttribute("aria-label") || (el as HTMLInputElement).labels?.[0]?.textContent || el.textContent || "").trim();
      const controls = [...document.querySelectorAll("input:not([type=hidden]), select, textarea, button")].filter((el) => name(el) === "");
      const levels = [...document.querySelectorAll("main h1, main h2, main h3, main h4")].map((h) => Number(h.tagName[1]));
      const skips = levels.filter((level, i) => i > 0 && level - levels[i - 1] > 1);
      return { unnamed: controls.length, skips: skips.length, h1: document.querySelectorAll("h1").length };
    });
    expect(problems).toEqual({ unnamed: 0, skips: 0, h1: 1 });
  });

  test("a phone-width screen has no sideways scrolling", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await mockApi(page);
    await signIn(page);
    await openDraft(page);
    const wide = await page.evaluate(() => {
      const width = document.documentElement.clientWidth;
      const sticking = [...document.querySelectorAll("main *")]
        .filter((el) => {
          const r = el.getBoundingClientRect();
          // A table inside .ws-table-wrap may scroll on its own; only the page itself must not.
          return r.width > 0 && r.right > width + 1 && !el.closest(".ws-table-wrap");
        })
        .slice(0, 8)
        .map((el) => `${el.tagName.toLowerCase()}.${String(el.className).slice(0, 40)}`);
      return { extra: document.documentElement.scrollWidth - width, sticking };
    });
    expect(wide).toEqual({ extra: 0, sticking: [] });
  });

  test("a signed-out visitor is asked to sign in and is shown no case data", async ({ page }) => {
    await mockApi(page);
    await page.goto("/recommendations");
    await expect(page.getByRole("heading", { name: /sign in to view UW Analyzer recommendations/i })).toBeVisible();
    await expect(page.getByText("NIKE, Inc.")).toHaveCount(0);
    await page.goto(`/cases/${CASE_ID}?tab=recommendation`);
    await expect(page.getByRole("heading", { name: /sign in to view case/i })).toBeVisible();
    await expect(page.getByText("USD 3.75m")).toHaveCount(0);
  });

  test("a role without the decision permission sees no decision form", async ({ page }) => {
    await mockApi(page, { permissions: ["case:read"] });
    await signIn(page);
    await openDraft(page);
    await expect(page.getByText("No decision has been recorded. Your role cannot record one.")).toBeVisible();
    await expect(page.getByRole("button", { name: /Record my decision/ })).toHaveCount(0);
    await expect(page.getByText("Your role cannot record a published rating.")).toBeVisible();
  });
});
