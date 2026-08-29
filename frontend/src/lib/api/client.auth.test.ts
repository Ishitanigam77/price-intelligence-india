import { afterEach, describe, expect, it, vi } from "vitest";

import { apiGet, apiPost } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";

describe("authenticated API client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends the bearer token on GET and never a client user id", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [], total: 0, limit: 50, offset: 0 }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await apiGet(
      "/watchlists",
      { user_id: "should-be-query-only-if-passed" },
      { accessToken: "session-token" },
    );

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/v1/watchlists");
    expect(String(url)).toContain("user_id=should-be-query-only-if-passed");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer session-token");
  });

  it("posts JSON without attaching a user_id", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({ id: "wl-1", product_id: "p-1" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await apiPost("/watchlists", { product_id: "p-1" }, { accessToken: "session-token" });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({ product_id: "p-1" });
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer session-token");
  });

  it("maps 401 onto ApiError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({
          error: { code: "unauthenticated", message: "Authentication required." },
        }),
      }),
    );

    const error = await apiGet("/watchlists").catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 401, code: "unauthenticated" });
  });
});
