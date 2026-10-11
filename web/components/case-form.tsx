"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";

import { ApiErrorState } from "@/components/api-error-state";
import { useSession } from "@/components/session-provider";
import {
  ApiRequestError,
  createCase,
  getCase,
  updateCase,
  type CaseCreate,
  type CaseRecord,
  type CaseUpdate,
} from "@/lib/api/client";

type CaseFormProps =
  | { mode: "create"; caseId?: never }
  | { mode: "edit"; caseId: string };

type FormValues = {
  address: string;
  context: string;
  exposure_amount: string;
  exposure_currency: string;
  industry: string;
  jurisdiction: string;
  legal_name: string;
  parent_name: string;
  registration_number: string;
  terms: string;
  trading_name: string;
  ubo_name: string;
  website: string;
};

type FormErrors = Partial<Record<keyof FormValues, string>>;

const emptyValues: FormValues = {
  address: "",
  context: "",
  exposure_amount: "",
  exposure_currency: "",
  industry: "",
  jurisdiction: "",
  legal_name: "",
  parent_name: "",
  registration_number: "",
  terms: "",
  trading_name: "",
  ubo_name: "",
  website: "",
};

const optionalFields: (keyof FormValues)[] = [
  "address",
  "context",
  "industry",
  "jurisdiction",
  "legal_name",
  "parent_name",
  "registration_number",
  "terms",
  "trading_name",
  "ubo_name",
  "website",
];

function valuesFromRecord(record: CaseRecord): FormValues {
  return {
    address: record.address ?? "",
    context: record.context ?? "",
    exposure_amount: record.exposure_amount ?? "",
    exposure_currency: record.exposure_currency ?? "",
    industry: record.industry ?? "",
    jurisdiction: record.jurisdiction ?? "",
    legal_name: record.legal_name ?? "",
    parent_name: record.parent_name ?? "",
    registration_number: record.registration_number ?? "",
    terms: record.terms ?? "",
    trading_name: record.trading_name ?? "",
    ubo_name: record.ubo_name ?? "",
    website: record.website ?? "",
  };
}

function validate(values: FormValues): FormErrors {
  const errors: FormErrors = {};
  const amount = values.exposure_amount.trim();
  const currency = values.exposure_currency.trim();

  if (!values.legal_name.trim() && !values.trading_name.trim()) {
    errors.legal_name = "Enter a legal name or a trading name.";
    errors.trading_name = "Enter a legal name or a trading name.";
  }

  if ((amount && !currency) || (!amount && currency)) {
    errors.exposure_amount = "Exposure amount and currency must be entered together.";
    errors.exposure_currency = "Exposure amount and currency must be entered together.";
  }

  if (amount && !/^\d{1,16}(?:\.\d{1,2})?$/.test(amount)) {
    errors.exposure_amount = "Use an exact non-negative amount with up to two decimal places.";
  }

  if (currency && !/^[A-Za-z]{3}$/.test(currency)) {
    errors.exposure_currency = "Use a three-letter currency code, for example CAD.";
  }

  const website = values.website.trim();
  if (website && !/^https?:\/\//i.test(website)) {
    errors.website = "Website must start with http:// or https://.";
  }

  return errors;
}

function createPayload(values: FormValues): CaseCreate {
  const payload: CaseCreate = {};

  for (const field of optionalFields) {
    const value = values[field].trim();
    if (value) payload[field] = value;
  }

  if (values.exposure_amount.trim()) {
    payload.exposure_amount = values.exposure_amount.trim();
    payload.exposure_currency = values.exposure_currency.trim().toUpperCase();
  }

  return payload;
}

function updatePayload(values: FormValues, record: CaseRecord): CaseUpdate {
  const payload: CaseUpdate = { expected_version: record.version };
  const identityLocked = record.status === "ENTITY_RESOLVED";

  for (const field of optionalFields) {
    if (identityLocked && ["jurisdiction", "legal_name", "registration_number"].includes(field)) {
      continue;
    }
    payload[field] = values[field].trim() || null;
  }

  payload.exposure_amount = values.exposure_amount.trim() || null;
  payload.exposure_currency = values.exposure_currency.trim().toUpperCase() || null;
  return payload;
}

export function CaseForm({ mode, caseId }: CaseFormProps) {
  const router = useRouter();
  const { session } = useSession();
  const [record, setRecord] = useState<CaseRecord>();
  const [values, setValues] = useState<FormValues>(emptyValues);
  const [errors, setErrors] = useState<FormErrors>({});
  const [loadError, setLoadError] = useState<ApiRequestError>();
  const [saveError, setSaveError] = useState<ApiRequestError>();
  const [conflictMessage, setConflictMessage] = useState<string>();
  const [isLoading, setIsLoading] = useState(mode === "edit" && Boolean(session));
  const [isSaving, setIsSaving] = useState(false);
  const canWrite = session?.user.permissions.includes("case:write") ?? false;

  useEffect(() => {
    if (mode !== "edit" || !session) return;

    const controller = new AbortController();
    setIsLoading(true);
    getCase(session.token, caseId, controller.signal)
      .then((nextRecord) => {
        setRecord(nextRecord);
        setValues(valuesFromRecord(nextRecord));
      })
      .catch((caughtError: unknown) => {
        if (controller.signal.aborted) return;
        setLoadError(
          caughtError instanceof ApiRequestError
            ? caughtError
            : new ApiRequestError({
                code: "unexpected_error",
                message: "The case could not be loaded. Try again.",
                retryable: true,
                status: 0,
              }),
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });

    return () => controller.abort();
  }, [caseId, mode, session]);

  function setField(field: keyof FormValues, value: string) {
    setValues((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session || !canWrite) return;

    const clientErrors = validate(values);
    if (Object.keys(clientErrors).length) {
      setErrors(clientErrors);
      return;
    }

    setErrors({});
    setSaveError(undefined);
    setConflictMessage(undefined);
    setIsSaving(true);

    try {
      let destination = "/cases";
      if (mode === "create") {
        const created = await createCase(session.token, createPayload(values));
        destination = `/cases/${created.id}`; // go straight to the case to choose the entity
      } else if (record) {
        await updateCase(session.token, caseId, updatePayload(values, record));
        destination = `/cases/${caseId}`;
      }
      router.push(destination);
    } catch (caughtError: unknown) {
      const apiError =
        caughtError instanceof ApiRequestError
          ? caughtError
          : new ApiRequestError({
              code: "unexpected_error",
              message: "The case could not be saved. Try again.",
              retryable: true,
              status: 0,
            });

      if (apiError.fieldErrors.length) {
        setErrors(
          Object.fromEntries(
            apiError.fieldErrors.map(({ field, message }) => [field.split(".").at(-1), message]),
          ) as FormErrors,
        );
      }

      if (mode === "edit" && apiError.status === 409) {
        setConflictMessage(apiError.message);
        try {
          const latest = await getCase(session.token, caseId);
          setRecord(latest);
          setValues(valuesFromRecord(latest));
        } catch (reloadError: unknown) {
          setLoadError(reloadError instanceof ApiRequestError ? reloadError : apiError);
        }
      } else {
        setSaveError(apiError);
      }
    } finally {
      setIsSaving(false);
    }
  }

  if (!session) {
    return (
      <section className="api-state-card">
        <p className="eyebrow">Local access required</p>
        <h1>Sign in to manage cases</h1>
        <p>The local development token is held in memory only.</p>
        <Link className="inline-action" href="/sign-in">Go to local sign in</Link>
      </section>
    );
  }

  if (!canWrite) {
    return (
      <section className="api-state-card" role="alert">
        <p className="eyebrow">Unable to continue</p>
        <h1>You don’t have access</h1>
        <p>Your account does not have permission to create or edit cases.</p>
      </section>
    );
  }

  if (isLoading) {
    return (
      <section aria-live="polite" className="api-state-card">
        <p className="eyebrow">Loading</p>
        <h1>Retrieving case details</h1>
      </section>
    );
  }

  if (loadError) return <ApiErrorState error={loadError} resourceName="Case" />;
  if (mode === "edit" && !record) return null;

  const identityLocked = record?.status === "ENTITY_RESOLVED";

  return (
    <section className="case-form-workspace">
      <header className="case-form-header">
        <div>
          <p className="eyebrow">{mode === "create" ? "Case intake" : "Case maintenance"}</p>
          <h1>{mode === "create" ? "New case" : "Edit case"}</h1>
          <p>
            Only a legal or trading name is required. Missing optional details remain visible as
            information gaps.
          </p>
        </div>
      </header>

      {identityLocked && (
        <div className="case-form-notice" role="note">
          The entity is resolved. Reopen it before changing the legal name, registration number, or
          jurisdiction.
        </div>
      )}

      {conflictMessage && (
        <div className="case-form-conflict" role="alert">
          <strong>{conflictMessage}</strong>
          <span>The latest case was reloaded. Review it and redo your edit.</span>
        </div>
      )}

      {saveError && (
        <div className="case-form-error" role="alert">
          <strong>{saveError.message}</strong>
          {saveError.requestId && (
            <details>
              <summary>Support details</summary>
              <code>Request ID: {saveError.requestId}</code>
            </details>
          )}
        </div>
      )}

      <form className="case-form" noValidate onSubmit={handleSubmit}>
        <fieldset>
          <legend>Entity identity</legend>
          <div className="case-form-grid">
            <Field
              disabled={identityLocked}
              error={errors.legal_name}
              label="Legal name"
              name="legal_name"
              onChange={setField}
              value={values.legal_name}
            />
            <Field
              error={errors.trading_name}
              label="Trading name"
              name="trading_name"
              onChange={setField}
              value={values.trading_name}
            />
            <Field
              disabled={identityLocked}
              error={errors.registration_number}
              label="Registration number"
              name="registration_number"
              onChange={setField}
              value={values.registration_number}
            />
            <Field
              disabled={identityLocked}
              error={errors.jurisdiction}
              label="Jurisdiction"
              name="jurisdiction"
              onChange={setField}
              value={values.jurisdiction}
            />
            <Field error={errors.website} label="Website" name="website" onChange={setField} value={values.website} />
            <Field error={errors.industry} label="Industry" name="industry" onChange={setField} value={values.industry} />
            <Field error={errors.parent_name} label="Parent name" name="parent_name" onChange={setField} value={values.parent_name} />
            <Field error={errors.ubo_name} label="Ultimate beneficial owner" name="ubo_name" onChange={setField} value={values.ubo_name} />
            <TextArea error={errors.address} label="Address" name="address" onChange={setField} value={values.address} />
          </div>
        </fieldset>

        <fieldset>
          <legend>Exposure and context</legend>
          <div className="case-form-grid">
            <Field
              error={errors.exposure_amount}
              inputMode="decimal"
              label="Exposure amount"
              name="exposure_amount"
              onChange={setField}
              value={values.exposure_amount}
            />
            <Field
              error={errors.exposure_currency}
              label="Exposure currency"
              maxLength={3}
              name="exposure_currency"
              onChange={setField}
              placeholder="CAD"
              value={values.exposure_currency}
            />
            <TextArea error={errors.terms} label="Requested terms" name="terms" onChange={setField} value={values.terms} />
            <TextArea error={errors.context} label="Case context" name="context" onChange={setField} value={values.context} />
          </div>
        </fieldset>

        <div className="case-form-actions">
          <Link className="secondary-action" href="/cases">Cancel</Link>
          <button className="primary-action" disabled={isSaving} type="submit">
            {isSaving ? "Saving…" : mode === "create" ? "Create case" : "Save changes"}
          </button>
        </div>
      </form>
    </section>
  );
}

type FieldProps = {
  disabled?: boolean;
  error?: string;
  inputMode?: "decimal";
  label: string;
  maxLength?: number;
  name: keyof FormValues;
  onChange: (name: keyof FormValues, value: string) => void;
  placeholder?: string;
  value: string;
};

function Field({ disabled, error, inputMode, label, maxLength, name, onChange, placeholder, value }: FieldProps) {
  const errorId = `${name}-error`;
  return (
    <label className="case-field">
      <span>{label}</span>
      <input
        aria-describedby={error ? errorId : undefined}
        aria-invalid={Boolean(error)}
        aria-label={label}
        disabled={disabled}
        inputMode={inputMode}
        maxLength={maxLength}
        name={name}
        onChange={(event) => onChange(name, event.target.value)}
        placeholder={placeholder}
        value={value}
      />
      {error && <small id={errorId}>{error}</small>}
    </label>
  );
}

function TextArea({ error, label, name, onChange, value }: FieldProps) {
  const errorId = `${name}-error`;
  return (
    <label className="case-field case-field-wide">
      <span>{label}</span>
      <textarea
        aria-describedby={error ? errorId : undefined}
        aria-invalid={Boolean(error)}
        aria-label={label}
        name={name}
        onChange={(event) => onChange(name, event.target.value)}
        rows={3}
        value={value}
      />
      {error && <small id={errorId}>{error}</small>}
    </label>
  );
}
