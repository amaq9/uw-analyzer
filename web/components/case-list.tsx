"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ApiErrorState } from "@/components/api-error-state";
import { useSession } from "@/components/session-provider";
import { ApiRequestError, listCases, type CaseRecord } from "@/lib/api/client";

const PAGE_SIZE = 10;

function readableStatus(status: string) {
  return status.toLowerCase().replaceAll("_", " ");
}

function caseName(record: CaseRecord) {
  return record.legal_name || record.trading_name || "Name not provided";
}

export function CaseList() {
  const { session } = useSession();
  const [page, setPage] = useState(0);
  const [records, setRecords] = useState<CaseRecord[]>([]);
  const [error, setError] = useState<ApiRequestError>();
  const [isLoading, setIsLoading] = useState(Boolean(session));
  const canWrite = session?.user.permissions.includes("case:write") ?? false;

  useEffect(() => {
    if (!session) return;

    const controller = new AbortController();
    setIsLoading(true);
    setError(undefined);

    listCases(session.token, PAGE_SIZE, page * PAGE_SIZE, controller.signal)
      .then(setRecords)
      .catch((caughtError: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          caughtError instanceof ApiRequestError
            ? caughtError
            : new ApiRequestError({
                code: "unexpected_error",
                message: "Cases could not be loaded. Try again.",
                retryable: true,
                status: 0,
              }),
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });

    return () => controller.abort();
  }, [page, session]);

  if (!session) {
    return (
      <section className="api-state-card">
        <p className="eyebrow">Local access required</p>
        <h1>Sign in to view cases</h1>
        <p>The local development token is held in memory only.</p>
        <Link className="inline-action" href="/sign-in">
          Go to local sign in
        </Link>
      </section>
    );
  }

  if (isLoading) {
    return (
      <section aria-live="polite" className="api-state-card">
        <p className="eyebrow">Loading</p>
        <h1>Retrieving cases</h1>
        <p>The newest cases are being loaded from the local API.</p>
      </section>
    );
  }

  if (error) return <ApiErrorState error={error} resourceName="Cases" />;

  return (
    <section className="cases-workspace">
      <header className="cases-header">
        <div>
          <p className="eyebrow">Case intake</p>
          <h1>Cases</h1>
          <p>Newest first. Information gaps remain visible until the missing details are supplied.</p>
        </div>
        {canWrite && (
          <Link className="primary-action" href="/cases/new">
            New case
          </Link>
        )}
      </header>

      {records.length ? (
        <div className="case-table-wrap">
          <table className="case-table">
            <thead>
              <tr>
                <th scope="col">Entity</th>
                <th scope="col">Jurisdiction</th>
                <th scope="col">Status</th>
                <th scope="col">Information gaps</th>
                <th scope="col">Updated</th>
                {canWrite && <th scope="col"><span className="visually-hidden">Actions</span></th>}
              </tr>
            </thead>
            <tbody>
              {records.map((record) => (
                <tr key={record.id}>
                  <td>
                    <strong>{caseName(record)}</strong>
                    {record.legal_name && record.trading_name && <span>{record.trading_name}</span>}
                  </td>
                  <td>{record.jurisdiction || "Not provided"}</td>
                  <td className="case-status">{readableStatus(record.status)}</td>
                  <td>{record.information_gaps.length}</td>
                  <td>{new Date(record.updated_at).toLocaleString()}</td>
                  {canWrite && (
                    <td>
                      <Link className="table-action" href={`/cases/${record.id}/edit`}>
                        Edit
                      </Link>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <section className="cases-empty">
          <p className="eyebrow">No records</p>
          <h2>No cases yet</h2>
          <p>Create a case when an entity is ready for research intake.</p>
          {canWrite && (
            <Link className="inline-action" href="/cases/new">
              Create the first case
            </Link>
          )}
        </section>
      )}

      <nav aria-label="Case pages" className="case-pagination">
        <button disabled={page === 0} onClick={() => setPage((value) => value - 1)} type="button">
          Previous
        </button>
        <span>Page {page + 1}</span>
        <button
          disabled={records.length < PAGE_SIZE}
          onClick={() => setPage((value) => value + 1)}
          type="button"
        >
          Next
        </button>
      </nav>
    </section>
  );
}
