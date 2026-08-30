import { describe, expect, it } from "vitest";

import { GET } from "@/app/health/route";

describe("frontend health route", () => {
  it("returns ok without exposing secrets", async () => {
    const response = GET();
    const body = (await response.json()) as { status: string; service: string };
    expect(response.status).toBe(200);
    expect(body.status).toBe("ok");
    expect(body.service).toBe("frontend");
    expect(JSON.stringify(body)).not.toMatch(/secret|token|password|clerk/i);
  });
});
