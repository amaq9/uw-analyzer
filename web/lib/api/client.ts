import { ApiConfigurationError, getApiBaseUrl } from "@/lib/api/config";
import type { components } from "@/lib/api/schema";

export type CurrentUser = components["schemas"]["Me"];
export type CaseCreate = components["schemas"]["CaseCreate"];
export type CaseRecord = components["schemas"]["CaseOut"];
export type CaseUpdate = components["schemas"]["CaseUpdate"];
export type DraftRecommendation = components["schemas"]["DraftOut"];
export type FieldError = components["schemas"]["FieldError"];
type ErrorResponse = components["schemas"]["ErrorResponse"];

export class ApiRequestError extends Error {
  readonly code: string;
  readonly fieldErrors: FieldError[];
  readonly requestId?: string;
  readonly retryable: boolean;
  readonly status: number;

  constructor({
    code,
    fieldErrors = [],
    message,
    requestId,
    retryable,
    status,
  }: {
    code: string;
    fieldErrors?: FieldError[];
    message: string;
    requestId?: string;
    retryable: boolean;
    status: number;
  }) {
    super(message);
    this.name = "ApiRequestError";
    this.code = code;
    this.fieldErrors = fieldErrors;
    this.requestId = requestId;
    this.retryable = retryable;
    this.status = status;
  }
}

function isErrorResponse(value: unknown): value is ErrorResponse {
  if (!value || typeof value !== "object" || !("error" in value)) return false;

  const error = value.error;
  return Boolean(
    error &&
      typeof error === "object" &&
      "code" in error &&
      typeof error.code === "string" &&
      "message" in error &&
      typeof error.message === "string" &&
      "correlation_id" in error &&
      typeof error.correlation_id === "string" &&
      "retryable" in error &&
      typeof error.retryable === "boolean",
  );
}

type RequestOptions = {
  body?: unknown;
  method?: "GET" | "PATCH" | "POST";
  signal?: AbortSignal;
};

async function requestJson<T>(
  path: string,
  token: string,
  { body, method = "GET", signal }: RequestOptions = {},
): Promise<T> {
  let response: Response;
  const headers: Record<string, string> = {
    Accept: "application/json",
    Authorization: `Bearer ${token}`,
  };

  if (body !== undefined) headers["Content-Type"] = "application/json";

  try {
    response = await fetch(`${getApiBaseUrl()}${path}`, {
      body: body === undefined ? undefined : JSON.stringify(body),
      headers,
      method,
      signal,
    });
  } catch (error) {
    if (error instanceof ApiConfigurationError) throw error;

    throw new ApiRequestError({
      code: "network_error",
      message: "UW Analyzer could not reach the local API. Confirm that it is running and try again.",
      retryable: true,
      status: 0,
    });
  }

  const requestId = response.headers.get("X-Request-ID") ?? undefined;

  if (!response.ok) {
    let body: unknown;

    try {
      body = await response.json();
    } catch {
      body = undefined;
    }

    if (isErrorResponse(body)) {
      throw new ApiRequestError({
        code: body.error.code,
        fieldErrors: body.error.field_errors ?? [],
        message: body.error.message,
        requestId: requestId ?? body.error.correlation_id,
        retryable: body.error.retryable,
        status: response.status,
      });
    }

    throw new ApiRequestError({
      code: "unexpected_response",
      message: "The API returned an unexpected response. Try again or quote the request ID to support.",
      requestId,
      retryable: response.status >= 500,
      status: response.status,
    });
  }

  return (await response.json()) as T;
}

export function getCurrentUser(token: string, signal?: AbortSignal) {
  return requestJson<CurrentUser>("/api/v1/me", token, { signal });
}

export function listCases(token: string, limit: number, offset: number, signal?: AbortSignal) {
  const query = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  return requestJson<CaseRecord[]>(`/api/v1/cases?${query}`, token, { signal });
}

export function getCase(token: string, caseId: string, signal?: AbortSignal) {
  return requestJson<CaseRecord>(`/api/v1/cases/${encodeURIComponent(caseId)}`, token, { signal });
}

export function createCase(token: string, input: CaseCreate, signal?: AbortSignal) {
  return requestJson<CaseRecord>("/api/v1/cases", token, {
    body: input,
    method: "POST",
    signal,
  });
}

export function updateCase(
  token: string,
  caseId: string,
  input: CaseUpdate,
  signal?: AbortSignal,
) {
  return requestJson<CaseRecord>(`/api/v1/cases/${encodeURIComponent(caseId)}`, token, {
    body: input,
    method: "PATCH",
    signal,
  });
}

export function getDraftRecommendation(
  token: string,
  caseId: string,
  draftId: string,
  signal?: AbortSignal,
) {
  return requestJson<DraftRecommendation>(
    `/api/v1/cases/${encodeURIComponent(caseId)}/draft-recommendations/${encodeURIComponent(draftId)}`,
    token,
    { signal },
  );
}
