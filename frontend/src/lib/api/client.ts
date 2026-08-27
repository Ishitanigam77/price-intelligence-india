import {
  getApiBaseUrl,
  getApiV1Prefix,
  getRequestTimeoutMs,
  getRetryPolicy,
} from "@/lib/api/config";
import { ApiError } from "@/lib/api/errors";
import type { ErrorResponse } from "@/lib/types/api";

type QueryValue = string | number | boolean | null | undefined;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function isRetryableStatus(status: number): boolean {
  return status === 429 || status >= 500;
}

function buildUrl(path: string, query?: Record<string, QueryValue>): string {
  const base = `${getApiBaseUrl()}${getApiV1Prefix()}`;
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const url = new URL(`${base}${normalizedPath}`);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value === null || value === undefined || value === "") {
        continue;
      }
      url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

async function parseError(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as ErrorResponse;
    if (body?.error?.message) {
      return new ApiError(
        response.status,
        body.error.code ?? "http_error",
        body.error.message,
        body.error.fields ?? null,
      );
    }
  } catch {
    // Fall through to a generic message when the body is not the standard envelope.
  }
  return new ApiError(
    response.status,
    "http_error",
    `Request failed with status ${response.status}.`,
  );
}

async function parseJson<T>(response: Response): Promise<T> {
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export async function apiGet<T>(path: string, query?: Record<string, QueryValue>): Promise<T> {
  const url = buildUrl(path, query);
  const { maxAttempts, backoffMs } = getRetryPolicy();
  const timeoutMs = getRequestTimeoutMs();
  let lastError: unknown;

  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      const response = await fetch(url, {
        method: "GET",
        headers: { Accept: "application/json" },
        cache: "no-store",
        signal: AbortSignal.timeout(timeoutMs),
      });
      if (!response.ok) {
        if (isRetryableStatus(response.status) && attempt < maxAttempts) {
          await sleep(backoffMs * 2 ** (attempt - 1));
          continue;
        }
        throw await parseError(response);
      }
      return await parseJson<T>(response);
    } catch (error) {
      lastError = error;
      if (error instanceof ApiError) {
        throw error;
      }
      if (attempt < maxAttempts) {
        await sleep(backoffMs * 2 ** (attempt - 1));
        continue;
      }
    }
  }

  throw lastError instanceof Error
    ? lastError
    : new ApiError(0, "network_error", "The request could not be completed.");
}
