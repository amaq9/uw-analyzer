import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DecisionForm } from "@/components/case/decision-form";
import { EvidenceTab } from "@/components/case/evidence-tab";
import { ReportTab } from "@/components/case/report-tab";
import { CaseWorkspace } from "@/components/case/workspace";
import { SessionProvider, type UserSession } from "@/components/session-provider";

const CASE_ID = "7cfadcf9-bc9c-4c37-ab74-9784507768cb";
const session: UserSession = {
  token: "local-test-token",
  user: {
    permissions: ["case:read", "case:write", "research:run", "decision:record", "report:complete"],
    roles: ["underwriter"],
    subject: "underwriter-demo",
    tenant_id: "demo-tenant",
  },
};
const originalBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

type Calls = { body?: string; method: string; url: string }[];

function stubApi(routes: Record<string, unknown>, calls: Calls = []) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      calls.push({ body: init?.body as string | undefined, method: init?.method ?? "GET", url });
      const key = Object.keys(routes).find((candidate) => String(url).includes(candidate));
      if (!key) return Promise.resolve(new Response("{}", { status: 404 }));
      return Promise.resolve(new Response(JSON.stringify(routes[key]), { status: 200 }));
    }),
  );
  return calls;
}

function wrap(children: React.ReactNode) {
  return render(<SessionProvider initialSession={session}>{children}</SessionProvider>);
}

const caseRecord = {
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
  information_gaps: [{ field: "address", description: "Address not provided." }],
  updated_at: "2026-10-11T20:00:00Z",
  created_at: "2026-10-11T20:00:00Z",
  version: 1,
};

beforeEach(() => {
  process.env.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000";
});

afterEach(() => {
  vi.unstubAllGlobals();
  if (originalBaseUrl === undefined) delete process.env.NEXT_PUBLIC_API_BASE_URL;
  else process.env.NEXT_PUBLIC_API_BASE_URL = originalBaseUrl;
});

describe("case workspace", () => {
  it("shows the case and every section, with money carrying its currency", async () => {
    stubApi({ [`/cases/${CASE_ID}`]: caseRecord });
    wrap(<CaseWorkspace caseId={CASE_ID} />);

    expect(await screen.findByRole("heading", { name: "NIKE, Inc." })).toBeInTheDocument();
    expect(screen.getByText("USD 5.00m")).toBeInTheDocument();
    for (const name of [
      "Overview",
      "Entity",
      "Documents",
      "Research",
      "Evidence and claims",
      "Review items",
      "UW Analyzer recommendation",
      "Final decision",
      "Report",
    ]) {
      expect(screen.getByRole("button", { name })).toBeInTheDocument();
    }
    expect(screen.queryByRole("button", { name: /approve|decline/i })).not.toBeInTheDocument();
  });

  it("names the browser tab after the case and the part being read", async () => {
    stubApi({ [`/cases/${CASE_ID}`]: caseRecord });
    wrap(<CaseWorkspace caseId={CASE_ID} />);
    await screen.findByRole("heading", { name: "NIKE, Inc." });
    expect(document.title).toBe("NIKE, Inc. · Overview · UW Analyzer");
    fireEvent.click(screen.getByRole("button", { name: "Final decision" }));
    await waitFor(() => expect(document.title).toBe("NIKE, Inc. · Final decision · UW Analyzer"));
  });

  it("asks for sign-in when there is no session", () => {
    render(
      <SessionProvider>
        <CaseWorkspace caseId={CASE_ID} />
      </SessionProvider>,
    );
    expect(screen.getByRole("link", { name: /local sign in/i })).toBeInTheDocument();
  });

  it("lets a person choose a candidate entity, and says research is blocked until then", async () => {
    const calls = stubApi({
      "/entity-candidates": [
        { id: "c1", case_id: CASE_ID, legal_name: "Acme Ltd", state: "candidate", registration_number: null, jurisdiction: "CA", website: null, address: null },
      ],
      "/research-readiness": {
        allowed: false,
        status: "DRAFT",
        blockers: [{ code: "entity_not_confirmed", message: "A person must confirm the legal entity before research can start." }],
      },
      "/entity-resolution": caseRecord,
      [`/cases/${CASE_ID}`]: { ...caseRecord, status: "DRAFT" },
    });
    wrap(<CaseWorkspace caseId={CASE_ID} />);
    fireEvent.click(await screen.findByRole("button", { name: "Entity" }));

    expect(await screen.findByText(/must confirm the legal entity/i)).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: /choose this entity/i }));
    await waitFor(() => expect(calls.some((call) => call.method === "POST" && call.url.endsWith("/entity-resolution"))).toBe(true));
    const post = calls.find((call) => call.method === "POST" && call.url.endsWith("/entity-resolution"));
    expect(JSON.parse(post?.body ?? "{}")).toMatchObject({ candidate_id: "c1" });
  });
});

describe("decision form", () => {
  const draft = { id: "d1", version: 2, requested_currency: "USD" } as never;

  function renderForm() {
    const calls = stubApi({ "/decision": { id: "x" } });
    wrap(<DecisionForm base={`/api/v1/cases/${CASE_ID}/draft-recommendations`} draft={draft} onDone={() => undefined} token="t" />);
    return calls;
  }

  it("adopts without a reason", async () => {
    const calls = renderForm();
    fireEvent.click(screen.getByRole("button", { name: /record my decision/i }));
    await waitFor(() => expect(calls).toHaveLength(1));
    expect(JSON.parse(calls[0].body ?? "{}")).toEqual({ action: "ADOPT" });
    expect(calls[0].url).toContain("/draft-recommendations/d1/decision");
  });

  it("requires a written reason to reject or change, and an amount to approve a change", async () => {
    const calls = renderForm();
    fireEvent.click(screen.getByLabelText(/reject it/i));
    const submit = screen.getByRole("button", { name: /record my decision/i });
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/reason/i), { target: { value: "Wrong entity." } });
    expect(submit).toBeEnabled();

    fireEvent.click(screen.getByLabelText(/change it/i));
    expect(submit).toBeDisabled(); // an amount is now needed
    fireEvent.change(screen.getByLabelText(/^amount/i), { target: { value: "600000" } });
    expect(submit).toBeEnabled();
    fireEvent.click(submit);
    await waitFor(() => expect(calls).toHaveLength(1));
    expect(JSON.parse(calls[0].body ?? "{}")).toEqual({
      action: "CHANGE",
      reason: "Wrong entity.",
      final_outcome: "APPROVE",
      final_amount: "600000",
    });
  });
});

describe("evidence and claims", () => {
  it("shows access and verification as separate things and has no control to set a status", async () => {
    stubApi({
      "/claims": [
        {
          id: "k1",
          case_id: CASE_ID,
          text: "The current ratio was 1.96x.",
          classification: "FACT",
          material: true,
          adverse: false,
          category: "FINANCIALS",
          freshness: "CURRENT",
          verification: { status: "VERIFIED", reasons: ["Supported by reliable evidence."], needs: [], conflict: false, rules_version: "1" },
          links: [
            {
              id: "l1",
              relation: "SUPPORTS",
              notes: null,
              evidence: {
                id: "e1",
                title: "NIKE FY2026 balance sheet data",
                origin: "sec.gov",
                source_class: "OFFICIAL",
                source_class_basis: "registry",
                discovery_only: false,
                accessed_at: "2026-10-11T16:29:54Z",
                kind: "CONNECTOR",
                event_on: "2026-05-31",
                published_on: "2026-07-15",
                excerpt: "current assets 24,603",
                url: null,
                provenance_ref: null,
              },
            },
          ],
        },
      ],
    });
    wrap(<EvidenceTab caseId={CASE_ID} onChanged={() => undefined} permissions={[]} token="t" />);

    expect(await screen.findByText("The current ratio was 1.96x.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Verification" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /linked evidence and access/i })).toBeInTheDocument();
    expect(screen.getByText("Verified")).toBeInTheDocument();
    expect(screen.getByText(/accessed/i, { selector: "p" })).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });
});

describe("an assessment rests on facts", () => {
  const evidence = {
    id: "e1",
    title: "NIKE annual report data for the year ended 2026-05-31",
    origin: "sec.gov",
    source_class: "OFFICIAL",
    source_class_basis: "registry",
    discovery_only: false,
    accessed_at: "2026-10-11T16:29:54Z",
    kind: "CONNECTOR",
    event_on: "2026-05-31",
    published_on: "2026-07-15",
    excerpt: "total assets 38,000",
    url: "https://www.sec.gov/Archives/edgar/data/320187/000032018726000088/",
    provenance_ref: null,
  };
  const fact = {
    id: "fact",
    case_id: CASE_ID,
    text: "At 2026-05-31 equity was USD 14.87bn.",
    classification: "FACT",
    material: true,
    adverse: false,
    category: "FINANCIALS",
    freshness: "CURRENT",
    basis_claim_ids: [],
    verification: { status: "VERIFIED", reasons: ["Supported by reliable evidence."], needs: [], conflict: false, rules_version: "1" },
    links: [{ id: "l1", relation: "SUPPORTS", notes: null, evidence }],
  };
  const assessment = {
    ...fact,
    id: "assessed",
    text: "Balance sheet strength: Strong (stable).",
    classification: "INTERPRETATION",
    basis_claim_ids: ["fact"],
    verification: {
      status: "NOT_APPLICABLE",
      reasons: ["This is an assessment worked out by the written rules from the facts it rests on, not a separate fact."],
      needs: [],
      conflict: false,
      rules_version: "1",
    },
    links: [],
  };

  it("shows the facts and the filing behind a rule-based assessment, and never says 'No evidence is linked'", async () => {
    stubApi({ "/claims": [assessment, fact] });
    wrap(<EvidenceTab caseId={CASE_ID} onChanged={() => undefined} permissions={[]} token="t" />);
    expect(await screen.findByText("Balance sheet strength: Strong (stable).")).toBeInTheDocument();
    expect(screen.getByText("Rule-based assessment")).toBeInTheDocument();
    expect(screen.queryByText(/judgement/i)).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Rests on these facts" })).toBeInTheDocument();
    expect(screen.getAllByText("At 2026-05-31 equity was USD 14.87bn.").length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText("No evidence is linked.")).not.toBeInTheDocument();
    const links = screen.getAllByRole("link", { name: "Open the web source" });
    expect(links.length).toBeGreaterThanOrEqual(2); // under the assessment and under the fact itself
    expect(links[0]).toHaveAttribute("href", evidence.url);
  });

  it("still says no evidence is linked when a fact really has none", async () => {
    stubApi({ "/claims": [{ ...fact, links: [], verification: { ...fact.verification, status: "UNVERIFIED" } }] });
    wrap(<EvidenceTab caseId={CASE_ID} onChanged={() => undefined} permissions={[]} token="t" />);
    expect(await screen.findByText("No evidence is linked.")).toBeInTheDocument();
  });
});

describe("report", () => {
  const content = {
    case_id: CASE_ID,
    as_of: "2026-10-11T20:00:00Z",
    notice: "Research report for the underwriter. It is not an underwriting decision.",
    test_product: true,
    financials_reviewed: [],
    verification_log: [],
    material_findings: [],
    unverified_claims: [],
    conflicts: [],
    information_gaps: [],
    limitations: ["No financial statements were reviewed."],
    adverse_search_statement: "An adverse search was not performed: no adverse-search source was accessed.",
    evidence_confidence: { level: "LOW", explanations: ["No source was accessed or recorded."], rules_version: "1" },
    counts: {
      connector_sources_accessed: 0, documents_reviewed: 0, web_sources_recorded: 0, material_claims: 0,
      verified_material_findings: 0, unverified_claims: 0, information_gaps: 0, open_escalations: 0, unavailable_sources: 0,
    },
    final_statement: "As of today.",
  };

  it("cannot be completed while a check fails, and says which one", async () => {
    stubApi({
      "/report-preview": {
        can_complete: false,
        gates: [{ code: "has_findings", passed: false, message: "Nothing has been recorded yet: add evidence and claims first." }],
        content,
      },
      "/reports": [],
    });
    wrap(<ReportTab caseId={CASE_ID} onChanged={() => undefined} permissions={["case:read", "report:complete"]} token="t" />);

    expect(await screen.findByText(/nothing has been recorded yet/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /complete the report/i })).toBeDisabled();
    expect(document.body).not.toHaveTextContent(/(?:^|\W)(?:approve|decline)(?:\W|$)/i);
    expect(screen.getByText(/no financial statements were reviewed/i, { selector: "p" })).toBeInTheDocument();
  });
});
