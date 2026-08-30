import { describe, expect, it } from "vitest";

import { safeExternalHref } from "@/lib/url/safeHref";

describe("safeExternalHref", () => {
  it("allows http and https URLs", () => {
    expect(safeExternalHref("https://mock-retailer-a.example.test/item")).toBe(
      "https://mock-retailer-a.example.test/item",
    );
    expect(safeExternalHref("http://localhost:3000/")).toBe("http://localhost:3000/");
  });

  it("rejects javascript, data, and malformed values", () => {
    expect(safeExternalHref("javascript:alert(1)")).toBeNull();
    expect(safeExternalHref("data:text/html,hi")).toBeNull();
    expect(safeExternalHref("not a url")).toBeNull();
    expect(safeExternalHref(null)).toBeNull();
  });
});
