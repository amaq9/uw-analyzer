"use client";

import { type FormEvent, useState } from "react";

import { StatementReview } from "@/components/case/statement-review";
import { type DocumentRecord, type TabProps, can } from "@/components/case/types";
import { ActionError, useAction, useLoad } from "@/components/use-api";
import { api, fetchBlob, uploadDocument } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { bytes, dateOnly, dateTime, readable } from "@/lib/format";

type Statement = components["schemas"]["StatementOut"];

export function DocumentsTab({ caseId, onChanged, permissions, token }: TabProps) {
  const base = `/api/v1/cases/${encodeURIComponent(caseId)}/documents`;
  const documents = useLoad((t, signal) => api<DocumentRecord[]>(t, "GET", base, undefined, signal), [caseId]);
  const upload = useAction();
  const download = useAction();
  const canWrite = can(permissions, "case:write");
  const statements = useLoad((t, signal) => api<Statement[]>(t, "GET", `/api/v1/cases/${encodeURIComponent(caseId)}/statements`, undefined, signal), [caseId]);
  const read = useAction();
  const [reading, setReading] = useState<{ documentId: string; extraction: components["schemas"]["ExtractionOut"] }>();

  async function readFigures(record: DocumentRecord) {
    const extraction = await read.run(() => api<components["schemas"]["ExtractionOut"]>(token, "GET", `${base}/${record.id}/figures-preview`));
    if (extraction) setReading({ documentId: record.id, extraction });
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const done = await upload.run(() => uploadDocument(token, caseId, data));
    if (done) {
      form.reset();
      documents.reload();
      onChanged();
    }
  }

  async function open(record: DocumentRecord) {
    const blob = await download.run(() => fetchBlob(token, `${base}/${record.id}/content`));
    if (!blob) return;
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = record.filename;
    link.click();
    URL.revokeObjectURL(url);
  }

  const list = documents.data ?? [];

  return (
    <div className="ws-stack">
      <section className="ws-card">
        <h2>Documents</h2>
        <p>
          Uploaded files are checked on their contents, scanned for viruses and stored privately. They can never be
          edited or deleted. Financial statements from public filers are fetched automatically, so uploads are optional.
        </p>
        {list.length === 0 ? (
          <p>No document has been uploaded.</p>
        ) : (
          <div className="ws-table-wrap">
            <table className="ws-table">
              <thead>
                <tr>
                  <th>File</th>
                  <th>Category</th>
                  <th>Size</th>
                  <th>Virus scan</th>
                  <th>Uploaded</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {list.map((record) => (
                  <tr key={record.id}>
                    <td>
                      <strong>{record.filename}</strong>
                      <small className="ws-muted">SHA-256 {record.sha256.slice(0, 12)}…</small>
                    </td>
                    <td>{readable(record.category)}</td>
                    <td>{bytes(record.size_bytes)}</td>
                    <td>{readable(record.scan_status)}</td>
                    <td>{dateTime(record.uploaded_at)}</td>
                    <td>
                      <button className="ws-button" onClick={() => open(record)} type="button">
                        Download
                      </button>
                      {canWrite && record.category === "financial_statement" && (
                        <button className="ws-button" disabled={read.busy} onClick={() => readFigures(record)} type="button">
                          Read figures
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <ActionError error={download.error} />
        <ActionError error={read.error} />
      </section>

      {reading && (
        <section className="ws-card">
          <StatementReview
            base={`/api/v1/cases/${encodeURIComponent(caseId)}`}
            documentId={reading.documentId}
            extraction={reading.extraction}
            onConfirmed={() => {
              statements.reload();
              onChanged();
            }}
            token={token}
          />
        </section>
      )}

      <section className="ws-card">
        <h3>Confirmed figures in use for the analysis</h3>
        {(statements.data ?? []).length === 0 ? (
          <p>None yet. Upload a financial statement, press Read figures, check them and confirm.</p>
        ) : (
          <div className="ws-table-wrap">
            <table className="ws-table">
              <thead>
                <tr>
                  <th>Period ending</th>
                  <th>Currency and unit</th>
                  <th>Statements</th>
                  <th>Figures</th>
                  <th>Confirmed</th>
                </tr>
              </thead>
              <tbody>
                {(statements.data ?? []).map((statement) => (
                  <tr key={statement.id}>
                    <td>{dateOnly(statement.period_end)}</td>
                    <td>
                      {statement.currency}, {statement.unit}
                    </td>
                    <td>{readable(statement.audit_status)}</td>
                    <td>{Object.keys(statement.figures).length} figures</td>
                    <td>
                      {statement.confirmed_by}, {dateTime(statement.confirmed_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {canWrite && (
        <section className="ws-card">
          <h3>Upload a document</h3>
          <form className="ws-form" onSubmit={submit}>
            <label className="ws-field">
              Category
              <select aria-label="Category" defaultValue="financial_statement" name="category">
                <option value="financial_statement">Financial statement</option>
                <option value="credit_report">Credit report</option>
                <option value="supporting">Supporting document</option>
              </select>
            </label>
            <label className="ws-field">
              File (PDF, Word, Excel, CSV, text, PNG or JPEG, up to 20 MB)
              <input name="file" required type="file" />
            </label>
            <button className="ws-button primary" disabled={upload.busy} type="submit">
              {upload.busy ? "Checking and storing…" : "Upload"}
            </button>
            <ActionError error={upload.error} />
          </form>
        </section>
      )}
    </div>
  );
}
