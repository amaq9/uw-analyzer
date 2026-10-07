import Link from "next/link";

import { Brand } from "@/components/brand";
import { DevTokenSignIn } from "@/components/dev-token-sign-in";
import { LockIcon, ShieldIcon } from "@/components/icons";

export default function SignInPage() {
  return (
    <main className="access-page">
      <section className="access-story">
        <Brand />
        <div className="access-story-copy">
          <p className="eyebrow">Secure research workspace</p>
          <h1>Trust the trail,<br />not the black box.</h1>
          <p>
            Research legal entities, test claims against evidence, and hand the final judgment to the
            underwriter with the full context intact.
          </p>
        </div>
        <div className="access-principle">
          <ShieldIcon />
          <p>
            <strong>Designed for accountability.</strong>
            Every material finding is linked to its source, access record, and review state.
          </p>
        </div>
      </section>

      <section className="access-form" aria-labelledby="access-title">
        <div className="access-card">
          <div className="access-lock"><LockIcon /></div>
          <p className="eyebrow">Enterprise access</p>
          <h2 id="access-title">Sign in to your workspace</h2>
          <p className="access-intro">
            Access is managed through your organization’s identity provider. Local passwords are not
            stored by UW Analyzer.
          </p>
          <button className="sso-button" type="button" disabled>
            Continue with enterprise SSO
          </button>
          <p className="configuration-note">Identity provider connection is being configured.</p>
          {process.env.NODE_ENV === "development" ? (
            <>
              <div className="access-divider"><span>Local pilot access</span></div>
              <DevTokenSignIn />
            </>
          ) : (
            <>
              <div className="access-divider"><span>Preview</span></div>
              <Link className="preview-link" href="/">View the workspace foundation</Link>
            </>
          )}
        </div>
        <p className="access-footer">Authorized internal users only · Activity will be audited</p>
      </section>
    </main>
  );
}
