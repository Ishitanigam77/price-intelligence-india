import { describe, expect, it } from "vitest";

import { isSensitiveKey, safePath, sanitizeTelemetryPayload } from "@/lib/observability/sanitize";

describe("frontend telemetry sanitization", () => {
  it("drops credential-looking keys and values", () => {
    expect(isSensitiveKey("authorization")).toBe(true);
    expect(isSensitiveKey("path")).toBe(false);
    const cleaned = sanitizeTelemetryPayload({
      path: "/search",
      authorization: "Bearer leaked",
      cookie: "session=abc",
      error_type: "TypeError",
      note: "Bearer super-secret",
    });
    expect(cleaned.path).toBe("/search");
    expect(cleaned.error_type).toBe("TypeError");
    expect(cleaned.authorization).toBeUndefined();
    expect(cleaned.cookie).toBeUndefined();
    expect(cleaned.note).toBeUndefined();
  });

  it("strips query strings from paths", () => {
    expect(safePath("/search?token=abc")).toBe("/search");
  });
});
