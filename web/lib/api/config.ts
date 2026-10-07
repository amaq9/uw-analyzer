export class ApiConfigurationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiConfigurationError";
  }
}

export function getApiBaseUrl() {
  const configuredUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();

  if (!configuredUrl) {
    throw new ApiConfigurationError(
      "The API connection is not configured. Set NEXT_PUBLIC_API_BASE_URL and restart the web app.",
    );
  }

  let parsedUrl: URL;

  try {
    parsedUrl = new URL(configuredUrl);
  } catch {
    throw new ApiConfigurationError("NEXT_PUBLIC_API_BASE_URL must be a valid URL.");
  }

  if (!['http:', 'https:'].includes(parsedUrl.protocol)) {
    throw new ApiConfigurationError("NEXT_PUBLIC_API_BASE_URL must use HTTP or HTTPS.");
  }

  return parsedUrl.toString().replace(/\/$/, "");
}
