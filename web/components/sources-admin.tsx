"use client";

import { type FormEvent } from "react";

import type { SourceRecord } from "@/components/case/types";
import { useSession } from "@/components/session-provider";
import { ActionError, Gate, useAction, useLoad } from "@/components/use-api";
import { api } from "@/lib/api/client";
import { readable } from "@/lib/format";

const ACCESS = ["ACTUALLY_ACCESSIBLE", "RESTRICTED_LICENSED", "DISCOVERY_ONLY", "TECHNICALLY_UNAVAILABLE"];
const HEALTH = ["UNKNOWN", "HEALTHY", "DEGRADED", "DOWN"];

function Row({ onChanged, source, token, canManage }: Readonly<{ canManage: boolean; onChanged: () => void; source: SourceRecord; token: string }>) {
  const action = useAction();

  async function change(field: "access_category" | "health", value: string) {
    const done = await action.run(() =>
      api(token, "PATCH", `/api/v1/sources/${source.id}`, { expected_version: source.version, [field]: value }),
    );
    if (done) onChanged();
  }

  return (
    <tr>
      <td>
        <strong>{source.name}</strong>
        <small className="ws-muted"> {source.key}</small>
        {source.terms_notes && <small className="ws-muted"> {source.terms_notes}</small>}
        <ActionError error={action.error} />
      </td>
      <td>
        {readable(source.source_class)}
        <small className="ws-muted"> {readable(source.source_type)}</small>
      </td>
      <td>{source.jurisdictions.join(", ")}</td>
      <td>
        {canManage ? (
          <select aria-label={`Access for ${source.name}`} disabled={action.busy} onChange={(event) => change("access_category", event.target.value)} value={source.access_category}>
            {ACCESS.map((value) => (
              <option key={value} value={value}>
                {readable(value)}
              </option>
            ))}
          </select>
        ) : (
          readable(source.access_category)
        )}
      </td>
      <td>{readable(source.auth_state)}</td>
      <td>
        {canManage ? (
          <select aria-label={`Health of ${source.name}`} disabled={action.busy} onChange={(event) => change("health", event.target.value)} value={source.health}>
            {HEALTH.map((value) => (
              <option key={value} value={value}>
                {readable(value)}
              </option>
            ))}
          </select>
        ) : (
          readable(source.health)
        )}
      </td>
    </tr>
  );
}

export function SourcesAdmin() {
  const { session } = useSession();
  const sources = useLoad((token, signal) => api<SourceRecord[]>(token, "GET", "/api/v1/sources", undefined, signal), []);
  const create = useAction();
  const canManage = session?.user.permissions.includes("admin:manage") ?? false;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    const done = await create.run(() =>
      api(session.token, "POST", "/api/v1/sources", {
        key: String(data.get("key")).trim(),
        name: String(data.get("name")).trim(),
        source_class: String(data.get("source_class")),
        source_type: String(data.get("source_type")).trim(),
        jurisdictions: String(data.get("jurisdictions")).split(/[\s,]+/).filter(Boolean),
        access_category: String(data.get("access_category")),
        auth_state: String(data.get("auth_state")),
        terms_notes: String(data.get("terms_notes")).trim() || null,
      }),
    );
    if (done) {
      form.reset();
      sources.reload();
    }
  }

  return (
    <Gate error={sources.error} loading={sources.loading} name="Sources" signedIn={Boolean(session)}>
      <section className="ws">
        <header className="ws-header">
          <div>
            <p className="eyebrow">Source access</p>
            <h1>Source registry</h1>
            <p className="ws-muted">
              What the product is able to reach. A registry entry is not proof that a source was used: only a logged
              connector call shows that. No credentials are stored here.
            </p>
          </div>
        </header>
        <section className="ws-card">
          <div className="ws-table-wrap">
            <table className="ws-table">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Class</th>
                  <th>Covers</th>
                  <th>Access</th>
                  <th>Credential</th>
                  <th>Health</th>
                </tr>
              </thead>
              <tbody>
                {(sources.data ?? []).map((source) => (
                  <Row canManage={canManage} key={source.id} onChanged={sources.reload} source={source} token={session?.token ?? ""} />
                ))}
              </tbody>
            </table>
          </div>
          {(sources.data ?? []).length === 0 && <p>No source is registered yet.</p>}
          {!canManage && <p className="ws-muted">Only an administrator can change the registry.</p>}
        </section>

        {canManage && (
          <section className="ws-card">
            <h3>Register a source</h3>
            <form className="ws-form" onSubmit={submit}>
              <label className="ws-field">
                Key (lowercase, for example ca-registry)
                <input name="key" required />
              </label>
              <label className="ws-field">
                Name
                <input name="name" required />
              </label>
              <label className="ws-field">
                Class
                <select name="source_class">
                  <option value="OFFICIAL">Official</option>
                  <option value="COMMERCIAL">Commercial</option>
                  <option value="SECONDARY">Secondary</option>
                  <option value="WEAK">Weak</option>
                </select>
              </label>
              <label className="ws-field">
                Type (company_registry, financial_filings, court_records, sanctions_list, news, macro_data)
                <input name="source_type" required />
              </label>
              <label className="ws-field">
                Countries (two-letter codes or GLOBAL)
                <input name="jurisdictions" required />
              </label>
              <label className="ws-field">
                Access
                <select name="access_category">
                  {ACCESS.map((value) => (
                    <option key={value} value={value}>
                      {readable(value)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="ws-field">
                Credential
                <select name="auth_state">
                  <option value="NOT_REQUIRED">Not required</option>
                  <option value="CONFIGURED">Configured</option>
                  <option value="MISSING">Missing</option>
                </select>
              </label>
              <label className="ws-field">
                Terms notes (optional)
                <input name="terms_notes" />
              </label>
              <button className="ws-button primary" disabled={create.busy} type="submit">
                Register source
              </button>
              <ActionError error={create.error} />
            </form>
          </section>
        )}
      </section>
    </Gate>
  );
}
