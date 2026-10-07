import { afterEach, describe, expect, it } from "vitest";

import { ApiConfigurationError, getApiBaseUrl } from "./config";

const originalBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

afterEach(() => {
  if (originalBaseUrl === undefined) {
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
  } else {
    process.env.NEXT_PUBLIC_API_BASE_URL = originalBaseUrl;
  }
});

describe("API base URL", () => {
  it("normalizes the configured URL", () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000/";

    expect(getApiBaseUrl()).toBe("http://127.0.0.1:8000");
  });

  it("fails clearly when configuration is absent", () => {
    delete process.env.NEXT_PUBLIC_API_BASE_URL;

    expect(() => getApiBaseUrl()).toThrow(ApiConfigurationError);
  });
});
