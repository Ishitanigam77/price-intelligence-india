import { describe, expect, it } from "vitest";

import { attachVerifiedPrices, groupSearchHits, variantPriceMap } from "@/lib/search/groupHits";
import {
  pricesFixture,
  retailerFixture,
  searchHitFixture,
  variantFixture,
} from "@/test/fixtures";

describe("groupSearchHits", () => {
  it("groups offers for the same variant without calculating price intelligence", () => {
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
    expect(first?.offerCount).toBe(2);
    expect(first?.cheapestRetailerName).toBeNull();
    expect(first?.observedMinPrice).toBeNull();
    expect(first?.observedMaxPrice).toBeNull();
    expect(first?.lowestVerifiedOffer).toBeNull();
  });
});

describe("attachVerifiedPrices", () => {
  it("copies backend comparison counts and displayed-price range onto search cards", () => {
    const grouped = groupSearchHits([searchHitFixture]);
    const attached = attachVerifiedPrices(
      grouped,
      variantPriceMap(searchHitFixture.product.id, [
        {
          ...pricesFixture.variants[0],
          offer_count: 3,
          distinct_retailer_count: 2,
          displayed_price_min: "18179.00",
          displayed_price_max: "22199.00",
        },
      ]),
    );

    expect(attached[0]?.offerCount).toBe(3);
    expect(attached[0]?.retailerCount).toBe(2);
    expect(attached[0]?.observedMinPrice).toBe("18179.00");
    expect(attached[0]?.observedMaxPrice).toBe("22199.00");
    expect(attached[0]?.cheapestRetailerName).toBe(
      pricesFixture.lowest_verified_offer?.retailer_name,
    );
    expect(attached[0]?.lowestVerifiedOffer?.offer_id).toBe(
      pricesFixture.lowest_verified_offer?.offer_id,
    );
  });
});
