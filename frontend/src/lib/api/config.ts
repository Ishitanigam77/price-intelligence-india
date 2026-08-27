import { ApiConfigError } from "@/lib/api/errors";

const DEFAULT_TIMEOUT_MS = 15_000;
const DEFAULT_MAX_ATTEMPTS = 3;
const DEFAULT_BACKOFF_MS = 200;

export function getApiBaseUrl(): string {
  const value = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!value) {
    throw new ApiConfigError(
      "NEXT_PUBLIC_API_BASE_URL is not configured. Set it in the environment (see frontend/.env.example).",
    );
  }
  return value.replace(/\/+$/, "");
}

export function getApiV1Prefix(): string {
  return "/api/v1";
}

export function getRequestTimeoutMs(): number {
  return DEFAULT_TIMEOUT_MS;
}

export function getRetryPolicy(): { maxAttempts: number; backoffMs: number } {
  return { maxAttempts: DEFAULT_MAX_ATTEMPTS, backoffMs: DEFAULT_BACKOFF_MS };
}
