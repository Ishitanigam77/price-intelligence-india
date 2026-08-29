import {
  getApiBaseUrl,
  getApiV1Prefix,
  getRequestTimeoutMs,
  getRetryPolicy,
} from "@/lib/api/config";
import { ApiError } from "@/lib/api/errors";
import type { ErrorResponse } from "@/lib/types/api";

type QueryValue = string | number | boolean | null | undefined;

export type ApiAuth = {
  accessToken?: string | null;
};

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

function buildHeaders(auth?: ApiAuth, hasBody?: boolean): HeadersInit {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (hasBody) {
    headers["Content-Type"] = "application/json";
  }
  if (auth?.accessToken) {
    headers.Authorization = `Bearer ${auth.accessToken}`;
  }
  return headers;
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

async function apiRequest<T>(
  method: string,
  path: string,
  options?: {
    query?: Record<string, QueryValue>;
    body?: unknown;
    auth?: ApiAuth;
    retryMutations?: boolean;
  },
): Promise<T> {
  const url = buildUrl(path, options?.query);
  const hasBody = options?.body !== undefined;
  const retryMutations = options?.retryMutations ?? false;
  const { maxAttempts, backoffMs } = getRetryPolicy();
  const timeoutMs = getRequestTimeoutMs();
  const attempts = method === "GET" || retryMutations ? maxAttempts : 1;
  let lastError: unknown;

  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      const response = await fetch(url, {
        method,
        headers: buildHeaders(options?.auth, hasBody),
        body: hasBody ? JSON.stringify(options?.body) : undefined,
        cache: "no-store",
        signal: AbortSignal.timeout(timeoutMs),
      });
      if (!response.ok) {
        if (isRetryableStatus(response.status) && attempt < attempts) {
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
      if (attempt < attempts) {
        await sleep(backoffMs * 2 ** (attempt - 1));
        continue;
      }
    }
  }

  throw lastError instanceof Error
    ? lastError
    : new ApiError(0, "network_error", "The request could not be completed.");
}

export async function apiGet<T>(
  path: string,
  query?: Record<string, QueryValue>,
  auth?: ApiAuth,
): Promise<T> {
  return apiRequest<T>("GET", path, { query, auth });
}

export async function apiPost<T>(path: string, body: unknown, auth?: ApiAuth): Promise<T> {
  return apiRequest<T>("POST", path, { body, auth });
}

export async function apiPatch<T>(path: string, body: unknown, auth?: ApiAuth): Promise<T> {
  return apiRequest<T>("PATCH", path, { body, auth });
}

export async function apiDelete(path: string, auth?: ApiAuth): Promise<void> {
  await apiRequest<void>("DELETE", path, { auth });
}
