"use client";

import Link from "next/link";
import { type ReactNode, useCallback, useEffect, useState } from "react";

import { ApiErrorState } from "@/components/api-error-state";
import { useSession } from "@/components/session-provider";
import { ApiRequestError } from "@/lib/api/client";

export function toApiError(caught: unknown, fallback: string) {
  return caught instanceof ApiRequestError
    ? caught
    : new ApiRequestError({ code: "unexpected_error", message: fallback, retryable: true, status: 0 });
}

/** Load something from the API with the signed-in token. `reload` fetches it again. */
export function useLoad<T>(load: (token: string, signal: AbortSignal) => Promise<T>, deps: unknown[]) {
  const { session } = useSession();
  const [data, setData] = useState<T>();
  const [error, setError] = useState<ApiRequestError>();
  const [loading, setLoading] = useState(Boolean(session));
  const [version, setVersion] = useState(0);
  const token = session?.token;

  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    setLoading(true);
    setError(undefined);
    load(token, controller.signal)
      .then(setData)
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) setError(toApiError(caught, "This could not be loaded. Try again."));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [token, version, ...deps]);

  const reload = useCallback(() => setVersion((value) => value + 1), []);
  return { data, error, loading, reload };
}

/** Shows sign-in, loading and error states, then the content. */
export function Gate({
  children,
  error,
  loading,
  name,
  signedIn,
}: Readonly<{
  children: ReactNode;
  error?: ApiRequestError;
  loading: boolean;
  name: string;
  signedIn: boolean;
}>) {
  if (!signedIn) {
    return (
      <section className="api-state-card">
        <p className="eyebrow">Local access required</p>
        <h1>Sign in to view {name.toLowerCase()}</h1>
        <p>The local test code is held in memory only and is cleared when the page is refreshed.</p>
        <Link className="inline-action" href="/sign-in">
          Go to local sign in
        </Link>
      </section>
    );
  }
  if (loading) {
    return (
      <section aria-live="polite" className="api-state-card">
        <p className="eyebrow">Loading</p>
        <h1>Retrieving {name.toLowerCase()}</h1>
      </section>
    );
  }
  if (error) return <ApiErrorState error={error} resourceName={name} />;
  return <>{children}</>;
}

/** Run a write action and keep its error message for display. */
export function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiRequestError>();

  async function run<T>(action: () => Promise<T>): Promise<T | undefined> {
    setBusy(true);
    setError(undefined);
    try {
      return await action();
    } catch (caught) {
      setError(toApiError(caught, "That did not work. Nothing was saved. Try again."));
      return undefined;
    } finally {
      setBusy(false);
    }
  }

  return { busy, error, run, clear: () => setError(undefined) };
}

export function ActionError({ error }: Readonly<{ error?: ApiRequestError }>) {
  if (!error) return null;
  return (
    <p className="ws-error" role="alert">
      {error.message}
      {error.fieldErrors.length > 0 && (
        <>
          {" "}
          {error.fieldErrors.map((field) => `${field.field}: ${field.message}`).join("; ")}
        </>
      )}
      {error.requestId && <small> Request ID: {error.requestId}</small>}
    </p>
  );
}
