import type { components } from "@/lib/api/schema";

type S = components["schemas"];

export type Candidate = S["CandidateOut"];
export type DocumentRecord = S["DocumentOut"];
export type Readiness = S["Readiness"];
export type RunRecord = S["RunOut"];
export type CallRecord = S["CallOut"];
export type ClaimRecord = S["ClaimOut"];
export type EvidenceRecord = S["EvidenceOut"];
export type EscalationList = S["EscalationList"];
export type EscalationRecord = S["EscalationOut"];
export type DraftRecord = S["DraftOut"];
export type DecisionRecord = S["DecisionOut"];
export type ReportPreview = S["Preview"];
export type ReportRecord = S["ReportOut"];
export type ReportSummary = S["ReportSummary"];
export type AgreementReport = S["AgreementReport"];
export type SourceRecord = S["SourceOut"];

export type TabProps = {
  caseId: string;
  token: string;
  permissions: string[];
  onChanged: () => void;
};

export function can(permissions: string[], permission: string) {
  return permissions.includes(permission);
}
