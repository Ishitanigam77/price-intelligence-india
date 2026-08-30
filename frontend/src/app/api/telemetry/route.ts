import { NextResponse } from "next/server";

import {
  applicationInsightsConfigured,
  getFrontendEnvironment,
  getFrontendServiceName,
} from "@/lib/observability/config";
import { sanitizeTelemetryPayload } from "@/lib/observability/sanitize";

type TelemetryBody = {
  event?: unknown;
  path?: unknown;
  duration_ms?: unknown;
  status?: unknown;
  error_type?: unknown;
};

const ALLOWED_EVENTS = new Set(["error", "navigation", "health"]);
const ALLOWED_STATUS = new Set(["ok", "error"]);
const MAX_BODY_BYTES = 4096;
const TELEMETRY_LIMIT_PER_MINUTE = 60;

const recentHits = new Map<string, number[]>();

function clientKey(request: Request): string {
  const forwarded = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  return (forwarded || request.headers.get("x-real-ip") || "unknown").slice(0, 128);
}

export function resetTelemetryRateLimitForTests(): void {
  recentHits.clear();
}

function allowTelemetry(key: string, now = Date.now()): boolean {
  const windowMs = 60_000;
  const cutoff = now - windowMs;
  const prior = (recentHits.get(key) ?? []).filter((stamp) => stamp > cutoff);
  if (prior.length >= TELEMETRY_LIMIT_PER_MINUTE) {
    recentHits.set(key, prior);
    return false;
  }
  prior.push(now);
  recentHits.set(key, prior);
  return true;
}

function originMatchesHost(request: Request): boolean {
  const origin = request.headers.get("origin");
  if (!origin) {
    return true;
  }
  const host = request.headers.get("host");
  if (!host) {
    return false;
  }
  try {
    return new URL(origin).host === host;
  } catch {
    return false;
  }
}

export async function POST(request: Request) {
  if (!originMatchesHost(request)) {
    return NextResponse.json({ status: "ignored" }, { status: 403 });
  }
  if (!allowTelemetry(clientKey(request))) {
    return NextResponse.json({ status: "rate_limited" }, { status: 429 });
  }

  const contentLength = Number(request.headers.get("content-length") ?? "0");
  if (Number.isFinite(contentLength) && contentLength > MAX_BODY_BYTES) {
    return NextResponse.json({ status: "ignored" }, { status: 413 });
  }

  let raw: string;
  try {
    raw = await request.text();
  } catch {
    return NextResponse.json({ status: "ignored" }, { status: 400 });
  }
  if (raw.length > MAX_BODY_BYTES) {
    return NextResponse.json({ status: "ignored" }, { status: 413 });
  }

  let body: TelemetryBody = {};
  try {
    body = JSON.parse(raw) as TelemetryBody;
  } catch {
    return NextResponse.json({ status: "ignored" }, { status: 400 });
  }

  const event = typeof body.event === "string" ? body.event : "";
  if (!ALLOWED_EVENTS.has(event)) {
    return NextResponse.json({ status: "ignored" }, { status: 400 });
  }

  const status =
    typeof body.status === "string" && ALLOWED_STATUS.has(body.status) ? body.status : "ok";
  const duration =
    typeof body.duration_ms === "number" && Number.isFinite(body.duration_ms)
      ? body.duration_ms
      : null;

  const sanitized = sanitizeTelemetryPayload({
    event,
    path: typeof body.path === "string" ? body.path : "/",
    duration_ms: duration,
    status,
    error_type: typeof body.error_type === "string" ? body.error_type : null,
    service: getFrontendServiceName(),
    environment: getFrontendEnvironment(),
  });

  console.info(
    JSON.stringify({
      timestamp: new Date().toISOString(),
      level: event === "error" ? "ERROR" : "INFO",
      message: `frontend.${event}`,
      ...sanitized,
      application_insights: applicationInsightsConfigured() ? "configured" : "not_configured",
    }),
  );

  return NextResponse.json({ status: "ok" });
}
