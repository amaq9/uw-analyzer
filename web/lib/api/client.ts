import { ApiConfigurationError, getApiBaseUrl } from "@/lib/api/config";
import type { components } from "@/lib/api/schema";

export type CurrentUser = components["schemas"]["Me"];
type ErrorResponse = components["schemas"]["ErrorResponse"];

export class ApiRequestError extends Error {
  readonly code: string;
  readonly requestId?: string;
  readonly retryable: boolean;
  readonly status: number;

  constructor({
    code,
    message,
    requestId,
    retryable,
    status,
  }: {
    code: string;
    message: string;
    requestId?: string;
    retryable: boolean;
    status: number;
  }) {
    super(message);
    this.name = "ApiRequestError";
    this.code = code;
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

export async function getCurrentUser(token: string, signal?: AbortSignal): Promise<CurrentUser> {
  let response: Response;

  try {
    response = await fetch(`${getApiBaseUrl()}/api/v1/me`, {
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${token}`,
      },
      method: "GET",
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

  return (await response.json()) as CurrentUser;
}
