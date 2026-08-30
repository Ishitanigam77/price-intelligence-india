import { safePath } from "@/lib/observability/sanitize";

export type FrontendTelemetryEvent = {
  event: "error" | "navigation" | "health";
  path?: string;
  duration_ms?: number;
  status?: string;
  error_type?: string;
};

export function reportFrontendEvent(event: FrontendTelemetryEvent): void {
  if (typeof window === "undefined") {
    return;
  }
  const payload = {
    event: event.event,
    path: event.path ? safePath(event.path) : safePath(window.location.pathname),
    duration_ms: event.duration_ms,
    status: event.status,
    error_type: event.error_type,
  };
  void fetch("/api/telemetry", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload),
    keepalive: true,
    cache: "no-store",
  }).catch(() => {
    // Telemetry must never break the UI.
  });
}

export function reportFrontendError(error: unknown, path?: string): void {
  const errorType = error instanceof Error ? error.name : "Error";
  reportFrontendEvent({
    event: "error",
    path,
    status: "error",
    error_type: errorType,
  });
}

export function reportFrontendNavigation(path: string, durationMs?: number): void {
  reportFrontendEvent({
    event: "navigation",
    path,
    duration_ms: durationMs,
    status: "ok",
  });
}
