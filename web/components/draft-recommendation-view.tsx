"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ApiErrorState } from "@/components/api-error-state";
import { useSession } from "@/components/session-provider";
import {
  ApiRequestError,
  getDraftRecommendation,
  type DraftRecommendation,
} from "@/lib/api/client";

type DraftRecommendationViewProps = {
  caseId: string;
  draftId: string;
};

function readableCode(value: string) {
  return value.toLowerCase().replaceAll("_", " ");
}

function amount(value: string | null, currency: string | null) {
  if (value === null) return "Not provided";
  return currency ? `${currency} ${value}` : value;
}

function EvidenceReference({
  evidence,
}: {
  evidence: DraftRecommendation["reasons"][number]["evidence"][number];
}) {
  return (
    <li className="draft-evidence-item">
      <div className="draft-evidence-heading">
        <strong>{evidence.kind === "web" ? "Web source" : "Case document"}</strong>
        {evidence.retrieved_at && (
          <span>Accessed {new Date(evidence.retrieved_at).toLocaleString()}</span>
        )}
      </div>
      <blockquote>“{evidence.quote}”</blockquote>
      {evidence.kind === "web" && evidence.url && (
        <a href={evidence.url} rel="noreferrer" target="_blank">
          Open source
        </a>
      )}
      {evidence.kind === "document" && evidence.document_id && (
        <p>
          Document <code>{evidence.document_id}</code>
          {evidence.location ? ` · ${evidence.location}` : ""}
        </p>
      )}
    </li>
  );
}

export function DraftRecommendationView({ caseId, draftId }: DraftRecommendationViewProps) {
  const { session } = useSession();
  const [draft, setDraft] = useState<DraftRecommendation>();
  const [error, setError] = useState<ApiRequestError>();
  const [isLoading, setIsLoading] = useState(Boolean(session));

  useEffect(() => {
    if (!session) return;

    const controller = new AbortController();
    setIsLoading(true);
    setError(undefined);

    getDraftRecommendation(session.token, caseId, draftId, controller.signal)
      .then(setDraft)
      .catch((caughtError: unknown) => {
        if (controller.signal.aborted) return;
        if (caughtError instanceof ApiRequestError) {
          setError(caughtError);
        } else {
          setError(
            new ApiRequestError({
              code: "unexpected_error",
              message: "The draft recommendation could not be loaded. Try again.",
              retryable: true,
              status: 0,
            }),
          );
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });

    return () => controller.abort();
  }, [caseId, draftId, session]);

  if (!session) {
    return (
      <section className="api-state-card">
        <p className="eyebrow">Local access required</p>
        <h1>Sign in to view this draft</h1>
        <p>The development token remains in memory only and is cleared when the page is refreshed.</p>
        <Link className="inline-action" href="/sign-in">
          Go to local sign in
        </Link>
      </section>
    );
  }

  if (isLoading) {
    return (
      <section aria-live="polite" className="api-state-card draft-loading">
        <p className="eyebrow">Loading</p>
        <h1>Retrieving the draft recommendation</h1>
        <p>Reasons and source references are being loaded from the local API.</p>
      </section>
    );
  }

  if (error) return <ApiErrorState error={error} resourceName="Draft recommendation" />;
  if (!draft) return null;

  return (
    <article className="draft-recommendation">
      <header className="draft-header">
        <div>
          <p className="eyebrow">Assisted underwriting</p>
          <h1>{draft.notice}</h1>
          <p className="draft-summary">{draft.summary}</p>
        </div>
      </header>

      <section aria-label="Draft recommendation overview" className="draft-overview">
        <dl>
          <div>
            <dt>Requested amount</dt>
            <dd>{amount(draft.requested_amount, draft.requested_currency)}</dd>
          </div>
          <div>
            <dt>Recommended amount</dt>
            <dd>{amount(draft.recommended_amount, draft.requested_currency)}</dd>
          </div>
          <div>
            <dt>Policy rules applied</dt>
            <dd>{draft.rule_codes.length ? draft.rule_codes.join(", ") : "Not recorded"}</dd>
          </div>
          <div>
            <dt>Draft version</dt>
            <dd>{draft.version}</dd>
          </div>
        </dl>
      </section>

      <div className="draft-content-grid">
        <section className="draft-section draft-reasons">
          <div className="section-heading compact">
            <div>
              <p className="eyebrow">Traceable rationale</p>
              <h2>Reasons and evidence</h2>
            </div>
          </div>
          {draft.reasons.length ? (
            <ol>
              {draft.reasons.map((reason, index) => (
                <li className="draft-reason" key={`${reason.text}-${index}`}>
                  <h3>{reason.text}</h3>
                  <ul>
                    {reason.evidence.map((evidence, evidenceIndex) => (
                      <EvidenceReference
                        evidence={evidence}
                        key={`${evidence.kind}-${evidence.document_id ?? evidence.url}-${evidenceIndex}`}
                      />
                    ))}
                  </ul>
                </li>
              ))}
            </ol>
          ) : (
            <p className="empty-record">No reasons or evidence references were recorded.</p>
          )}
        </section>

        <aside className="draft-side-column">
          <section className="draft-section">
            <p className="eyebrow">Amount context</p>
            <h2>Factors</h2>
            {draft.factors.length ? (
              <ul className="plain-record-list">
                {draft.factors.map((factor) => (
                  <li key={factor.code}>
                    <strong>{readableCode(factor.code)}</strong>
                    <span>{factor.explanation}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="empty-record">No lowering factors were recorded.</p>
            )}
          </section>

          <section className="draft-section draft-gaps">
            <p className="eyebrow">Known unknowns</p>
            <h2>Information gaps</h2>
            {draft.information_gaps.length ? (
              <ul className="plain-record-list">
                {draft.information_gaps.map((gap, index) => (
                  <li key={`${index}-${gap}`}>{gap}</li>
                ))}
              </ul>
            ) : (
              <p className="empty-record">No information gaps were recorded.</p>
            )}
          </section>

          <section className="draft-section draft-limitations">
            <p className="eyebrow">Use boundaries</p>
            <h2>Limitations</h2>
            {draft.limitations.length ? (
              <ul className="plain-record-list">
                {draft.limitations.map((limitation, index) => (
                  <li key={`${index}-${limitation}`}>{limitation}</li>
                ))}
              </ul>
            ) : (
              <p className="empty-record">No limitations were recorded.</p>
            )}
          </section>
        </aside>
      </div>

      <footer className="draft-metadata">
        <div>
          <span>Created by</span>
          <strong>{draft.created_by}</strong>
        </div>
        <div>
          <span>Created</span>
          <strong>{new Date(draft.created_at).toLocaleString()}</strong>
        </div>
        <div>
          <span>Model</span>
          <strong>{draft.source.model}</strong>
        </div>
        <div>
          <span>Skill version</span>
          <strong>{draft.source.skill_version}</strong>
        </div>
        <div>
          <span>Policy version</span>
          <strong>{draft.policy_version}</strong>
        </div>
      </footer>
    </article>
  );
}
