import { describe, expect, it } from "vitest";

import { groupSearchHits } from "@/lib/search/groupHits";
import { searchHitFixture, retailerFixture, variantFixture } from "@/test/fixtures";

describe("groupSearchHits", () => {
  it("groups offers for the same variant and reports retailer count and price range", () => {
    const second = {
      ...searchHitFixture,
      retailer: { ...retailerFixture, id: "99999999-9999-9999-9999-999999999999", slug: "mock-b" },
      displayed_price: "58499.00",
      retailer_product_id: "88888888-8888-8888-8888-888888888888",
    };
    const otherVariant = {
      ...searchHitFixture,
      variant: { ...variantFixture, id: "abababab-abab-abab-abab-abababababab", name: "256 GB" },
      displayed_price: "74499.00",
    };

    const grouped = groupSearchHits([searchHitFixture, second, otherVariant]);
    expect(grouped).toHaveLength(2);
    const first = grouped.find((card) => card.variant.id === variantFixture.id);
    expect(first?.retailerCount).toBe(2);
    expect(first?.observedMinPrice).toBe(58499);
    expect(first?.observedMaxPrice).toBe(59999);
  });
});
