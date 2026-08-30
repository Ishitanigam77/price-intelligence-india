import { afterEach, describe, expect, it } from "vitest";

import { POST, resetTelemetryRateLimitForTests } from "@/app/api/telemetry/route";

function telemetryRequest(
  body: unknown,
  init?: { origin?: string; host?: string; contentLength?: string },
): Request {
  const headers = new Headers({ "content-type": "application/json" });
  if (init?.host) {
    headers.set("host", init.host);
  } else {
    headers.set("host", "localhost:3000");
  }
  if (init?.origin) {
    headers.set("origin", init.origin);
  }
  const payload = JSON.stringify(body);
  if (init?.contentLength) {
    headers.set("content-length", init.contentLength);
  }
  return new Request("http://localhost:3000/api/telemetry", {
    method: "POST",
    headers,
    body: payload,
  });
}

describe("frontend telemetry route", () => {
  afterEach(() => {
    resetTelemetryRateLimitForTests();
  });

  it("accepts an allowlisted navigation event", async () => {
    const response = await POST(
      telemetryRequest({ event: "navigation", path: "/search", duration_ms: 12, status: "ok" }),
    );
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ status: "ok" });
  });

  it("rejects unknown events and cross-origin posts", async () => {
    const badEvent = await POST(telemetryRequest({ event: "probe" }));
    expect(badEvent.status).toBe(400);
    const crossOrigin = await POST(
      telemetryRequest(
        { event: "navigation", path: "/" },
        { origin: "https://evil.example.test", host: "localhost:3000" },
      ),
    );
    expect(crossOrigin.status).toBe(403);
  });

  it("rejects oversized payloads", async () => {
    const response = await POST(
      telemetryRequest({ event: "navigation", path: "/" }, { contentLength: "99999" }),
    );
    expect(response.status).toBe(413);
  });
});
