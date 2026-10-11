"use client";

import Link from "next/link";
import { useState } from "react";

import { DocumentsTab } from "@/components/case/documents-tab";
import { EntityTab } from "@/components/case/entity-tab";
import { EvidenceTab } from "@/components/case/evidence-tab";
import { RecommendationTab } from "@/components/case/recommendation-tab";
import { ReportTab } from "@/components/case/report-tab";
import { ResearchTab } from "@/components/case/research-tab";
import { ReviewTab } from "@/components/case/review-tab";
import { useSession } from "@/components/session-provider";
import { Gate, useLoad } from "@/components/use-api";
import { api, type CaseRecord } from "@/lib/api/client";
import { dateTime, money, readable } from "@/lib/format";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "entity", label: "Entity" },
  { id: "documents", label: "Documents" },
  { id: "research", label: "Research" },
  { id: "evidence", label: "Evidence and claims" },
  { id: "review", label: "Review items" },
  { id: "recommendation", label: "Draft recommendation" },
  { id: "report", label: "Report" },
] as const;

type TabId = (typeof TABS)[number]["id"];

function Overview({ record }: Readonly<{ record: CaseRecord }>) {
  const rows: [string, string][] = [
    ["Legal name", record.legal_name ?? "Not provided"],
    ["Trading name", record.trading_name ?? "Not provided"],
    ["Registration number", record.registration_number ?? "Not provided"],
    ["Jurisdiction", record.jurisdiction ?? "Not provided"],
    ["Industry", record.industry ?? "Not provided"],
    ["Parent", record.parent_name ?? "Not provided"],
    ["Website", record.website ?? "Not provided"],
    ["Requested exposure", money(record.exposure_amount, record.exposure_currency)],
    ["Terms", record.terms ?? "Not provided"],
    ["Owner", record.owner],
    ["Last updated", dateTime(record.updated_at)],
  ];
  return (
    <div className="ws-stack">
      <section className="ws-card">
        <h2>Case summary</h2>
        <dl className="ws-facts">
          {rows.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
        <p>
          <Link className="inline-action" href={`/cases/${record.id}/edit`}>
            Edit case details
          </Link>
        </p>
      </section>
      <section className="ws-card">
        <h3>Information gaps</h3>
        {record.information_gaps.length === 0 ? (
          <p>No gap in the intake details.</p>
        ) : (
          <ul className="ws-bullets">
            {record.information_gaps.map((gap) => (
              <li key={gap.field}>{gap.description}</li>
            ))}
          </ul>
        )}
      </section>
      <section className="ws-card">
        <h3>How a test run goes</h3>
        <ol className="ws-steps">
          <li>Entity: choose the exact legal entity (research stays blocked until you do).</li>
          <li>Research: plan the countries, start it, and watch the sources being tried.</li>
          <li>Ask for the case to be analysed: the analyst reads the sources and records findings and a draft.</li>
          <li>Evidence and claims: check what each finding rests on and how well it is verified.</li>
          <li>Review items: a reviewer resolves any disagreement between sources.</li>
          <li>Draft recommendation: read it, then record your own decision.</li>
          <li>Report: complete it once every check passes.</li>
        </ol>
      </section>
    </div>
  );
}

export function CaseWorkspace({ caseId }: Readonly<{ caseId: string }>) {
  const { session } = useSession();
  const record = useLoad(
    (token, signal) => api<CaseRecord>(token, "GET", `/api/v1/cases/${encodeURIComponent(caseId)}`, undefined, signal),
    [caseId],
  );
  const [tab, setTab] = useState<TabId>("overview");
  const data = record.data;

  return (
    <Gate error={record.error} loading={record.loading} name="Case" signedIn={Boolean(session)}>
      {data && session && (
        <section className="ws">
          <header className="ws-header">
            <div>
              <p className="eyebrow">Case</p>
              <h1>{data.legal_name ?? data.trading_name ?? "Unnamed case"}</h1>
              <p className="ws-muted">
                {readable(data.status)} · {data.jurisdiction ?? "Jurisdiction not provided"}
              </p>
            </div>
            <Link className="inline-action" href="/cases">
              All cases
            </Link>
          </header>
          <nav aria-label="Case sections" className="ws-tabs">
            {TABS.map((item) => (
              <button
                aria-current={tab === item.id ? "page" : undefined}
                className={tab === item.id ? "ws-tab active" : "ws-tab"}
                key={item.id}
                onClick={() => setTab(item.id)}
                type="button"
              >
                {item.label}
              </button>
            ))}
          </nav>
          {tab === "overview" && <Overview record={data} />}
          {tab === "entity" && (
            <EntityTab
              caseId={caseId}
              onChanged={record.reload}
              permissions={session.user.permissions}
              status={data.status}
              token={session.token}
            />
          )}
          {tab === "documents" && (
            <DocumentsTab caseId={caseId} onChanged={record.reload} permissions={session.user.permissions} token={session.token} />
          )}
          {tab === "research" && (
            <ResearchTab caseId={caseId} onChanged={record.reload} permissions={session.user.permissions} token={session.token} />
          )}
          {tab === "evidence" && (
            <EvidenceTab caseId={caseId} currency={data.exposure_currency} onChanged={record.reload} permissions={session.user.permissions} token={session.token} />
          )}
          {tab === "review" && (
            <ReviewTab caseId={caseId} onChanged={record.reload} permissions={session.user.permissions} token={session.token} />
          )}
          {tab === "recommendation" && (
            <RecommendationTab
              caseId={caseId}
              onChanged={record.reload}
              permissions={session.user.permissions}
              token={session.token}
            />
          )}
          {tab === "report" && (
            <ReportTab caseId={caseId} currency={data.exposure_currency} onChanged={record.reload} permissions={session.user.permissions} token={session.token} />
          )}
        </section>
      )}
    </Gate>
  );
}
