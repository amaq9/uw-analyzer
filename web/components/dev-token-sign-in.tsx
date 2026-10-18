"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { useSession } from "@/components/session-provider";
import { ApiRequestError } from "@/lib/api/client";
import { ApiConfigurationError } from "@/lib/api/config";

type SignInError = {
  message: string;
  requestId?: string;
};

export function DevTokenSignIn() {
  const [token, setToken] = useState("");
  const [error, setError] = useState<SignInError>();
  const [isSubmitting, setIsSubmitting] = useState(false);
  // Until the page is interactive the browser would submit the form itself, so the button waits.
  const [ready, setReady] = useState(false);
  useEffect(() => setReady(true), []);
  const { session, signIn, signOut: clearSession } = useSession();

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const submittedToken = token.trim();

    if (!submittedToken) {
      setError({ message: "Paste a local development token before continuing." });
      return;
    }

    setError(undefined);
    setIsSubmitting(true);

    try {
      await signIn(submittedToken);
      setToken("");
    } catch (caughtError) {
      setToken("");
      if (caughtError instanceof ApiRequestError) {
        setError({ message: caughtError.message, requestId: caughtError.requestId });
      } else if (caughtError instanceof ApiConfigurationError) {
        setError({ message: caughtError.message });
      } else {
        setError({ message: "Sign-in could not be completed. Try again." });
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleSignOut() {
    clearSession();
    setError(undefined);
  }

  if (session) {
    return (
      <section aria-labelledby="local-session-title" className="local-session">
        <div className="local-session-heading">
          <div>
            <p className="eyebrow">Local session active</p>
            <h3 id="local-session-title">Signed in as {session.user.subject}</h3>
          </div>
          <span className="local-status">Verified by /me</span>
        </div>
        <dl className="identity-details">
          <div>
            <dt>Tenant</dt>
            <dd>{session.user.tenant_id}</dd>
          </div>
          <div>
            <dt>Roles</dt>
            <dd>{session.user.roles.join(", ") || "None"}</dd>
          </div>
          <div>
            <dt>Permissions</dt>
            <dd>{session.user.permissions.join(", ") || "None"}</dd>
          </div>
        </dl>
        <Link className="dev-sign-in-button session-continue-link" href="/">
          Continue to workspace
        </Link>
        <button className="secondary-button" onClick={handleSignOut} type="button">
          End local session
        </button>
        <p className="memory-note">The token is held in memory only and is cleared on refresh.</p>
      </section>
    );
  }

  return (
    <form className="dev-token-form" onSubmit={handleSubmit}>
      <label htmlFor="development-token">Local development token</label>
      <textarea
        autoComplete="off"
        id="development-token"
        onChange={(event) => setToken(event.target.value)}
        placeholder="Paste a token printed by the local API"
        rows={3}
        spellCheck={false}
        value={token}
      />
      <button className="dev-sign-in-button" disabled={isSubmitting || !ready} type="submit">
        {isSubmitting ? "Checking access…" : "Continue to local workspace"}
      </button>
      <p className="memory-note">Development only · The token is kept in memory, never local storage.</p>
      {error && (
        <div aria-live="polite" className="access-error" role="alert">
          <strong>Access could not be verified</strong>
          <span>{error.message}</span>
          {error.requestId && <small>Request ID: {error.requestId}</small>}
        </div>
      )}
    </form>
  );
}
