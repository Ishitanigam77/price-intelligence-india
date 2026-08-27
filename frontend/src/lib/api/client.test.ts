import { afterEach, describe, expect, it, vi } from "vitest";

import { apiGet } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { searchPageFixture } from "@/test/fixtures";

describe("API client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("maps a success response onto the typed payload", async () => {
    const payload = searchPageFixture();
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => payload,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await apiGet("/products/search", { q: "aurora" });

    expect(result).toEqual(payload);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const calledUrl = String(fetchMock.mock.calls[0]?.[0]);
    expect(calledUrl).toBe("http://localhost:8000/api/v1/products/search?q=aurora");
  });

  it("throws ApiError with the backend envelope on a failure response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({
          error: { code: "not_found", message: "Product missing.", fields: null },
        }),
      }),
    );

    const error = await apiGet("/products/missing").catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 404,
      code: "not_found",
      message: "Product missing.",
    });
  });
});
