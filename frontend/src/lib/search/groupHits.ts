import { bestAvailability } from "@/lib/format/availability";
import type {
  AvailabilityStatus,
  ComparedOfferRead,
  MoneyAmount,
  ProductRead,
  ProductSearchHit,
  ProductSearchPage,
  ProductVariantRead,
  VariantPricesRead,
} from "@/lib/types/api";

export interface GroupedSearchCard {
  product: ProductRead;
  variant: ProductVariantRead;
  hits: ProductSearchHit[];
  retailerCount: number;
  offerCount: number;
  cheapestRetailerName: string | null;
  observedMinPrice: MoneyAmount | null;
  observedMaxPrice: MoneyAmount | null;
  currency: string;
  availability: AvailabilityStatus;
  lastUpdated: string | null;
  lowestVerifiedOffer: ComparedOfferRead | null;
}

function priceKey(productId: string, variantId: string): string {
  return `${productId}::${variantId}`;
}

export function groupSearchHits(hits: ProductSearchHit[]): GroupedSearchCard[] {
  const groups = new Map<string, GroupedSearchCard>();

  for (const hit of hits) {
    const key = priceKey(hit.product.id, hit.variant.id);
    const existing = groups.get(key);
    if (existing) {
      existing.hits.push(hit);
      continue;
    }
    groups.set(key, {
      product: hit.product,
      variant: hit.variant,
      hits: [hit],
      retailerCount: 0,
      offerCount: 0,
      cheapestRetailerName: null,
      observedMinPrice: null,
      observedMaxPrice: null,
      currency: hit.currency,
      availability: hit.availability,
      lastUpdated: hit.observed_at,
      lowestVerifiedOffer: null,
    });
  }

  return Array.from(groups.values()).map(finalizeGroup);
}

function finalizeGroup(group: GroupedSearchCard): GroupedSearchCard {
  const timestamps = group.hits.map((hit) => hit.observed_at).filter(Boolean);
  timestamps.sort();

  return {
    ...group,
    retailerCount: new Set(group.hits.map((hit) => hit.retailer.id)).size,
    offerCount: group.hits.length,
    cheapestRetailerName: null,
    observedMinPrice: null,
    observedMaxPrice: null,
    currency: group.hits[0]?.currency ?? group.currency,
    availability: bestAvailability(group.hits.map((hit) => hit.availability)),
    lastUpdated: timestamps.at(-1) ?? null,
  };
}

export function attachVerifiedPrices(
  cards: GroupedSearchCard[],
  variantPricesByKey: Map<string, VariantPricesRead>,
): GroupedSearchCard[] {
  return cards.map((card) => {
    const prices = variantPricesByKey.get(priceKey(card.product.id, card.variant.id));
    if (!prices) {
      return card;
    }
    return {
      ...card,
      retailerCount: prices.distinct_retailer_count,
      offerCount: prices.offer_count,
      cheapestRetailerName: prices.lowest_verified_offer?.retailer_name ?? null,
      observedMinPrice: prices.displayed_price_min,
      observedMaxPrice: prices.displayed_price_max,
      lowestVerifiedOffer: prices.lowest_verified_offer ?? null,
    };
  });
}

export function variantPriceMap(
  productId: string,
  variants: VariantPricesRead[],
): Map<string, VariantPricesRead> {
  const map = new Map<string, VariantPricesRead>();
  for (const variant of variants) {
    map.set(priceKey(productId, variant.variant_id), variant);
  }
  return map;
}

export function summarizeSearchPage(page: ProductSearchPage): {
  consulted: number;
  failed: number;
} {
  return {
    consulted: page.consulted_retailer_ids.length,
    failed: page.failures.length,
  };
}
