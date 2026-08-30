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

export async function POST(request: Request) {
  let body: TelemetryBody = {};
  try {
    body = (await request.json()) as TelemetryBody;
  } catch {
    return NextResponse.json({ status: "ignored" }, { status: 400 });
  }

  const event = typeof body.event === "string" ? body.event : "";
  if (!ALLOWED_EVENTS.has(event)) {
    return NextResponse.json({ status: "ignored" }, { status: 400 });
  }

  const sanitized = sanitizeTelemetryPayload({
    event,
    path: typeof body.path === "string" ? body.path : "/",
    duration_ms: typeof body.duration_ms === "number" ? body.duration_ms : null,
    status: typeof body.status === "string" ? body.status : "ok",
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
