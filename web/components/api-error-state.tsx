import Link from "next/link";

import { ApiRequestError } from "@/lib/api/client";

type ApiErrorStateProps = {
  error: ApiRequestError;
  resourceName: string;
};

export function ApiErrorState({ error, resourceName }: ApiErrorStateProps) {
  const heading =
    error.status === 403
      ? "You don’t have access"
      : error.status === 404
        ? `${resourceName} not found`
        : error.status === 401
          ? "Your local session has expired"
          : `Could not load ${resourceName.toLowerCase()}`;

  return (
    <section aria-live="polite" className="api-state-card" role="alert">
      <p className="eyebrow">Unable to continue</p>
      <h1>{heading}</h1>
      <p>{error.message}</p>
      {error.status === 401 && (
        <Link className="inline-action" href="/sign-in">
          Return to sign in
        </Link>
      )}
      {error.requestId && (
        <details>
          <summary>Support details</summary>
          <code>Request ID: {error.requestId}</code>
        </details>
      )}
    </section>
  );
}
