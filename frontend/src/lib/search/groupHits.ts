import { bestAvailability } from "@/lib/format/availability";
import { parseMoney } from "@/lib/format/money";
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
  const retailerIds = new Set(group.hits.map((hit) => hit.retailer.id));
  const prices = group.hits
    .map((hit) => parseMoney(hit.displayed_price))
    .filter((value): value is number => value !== null);
  const timestamps = group.hits.map((hit) => hit.observed_at).filter(Boolean);
  timestamps.sort();
  const min = prices.length ? Math.min(...prices) : null;
  const max = prices.length ? Math.max(...prices) : null;

  return {
    ...group,
    retailerCount: retailerIds.size,
    observedMinPrice: min,
    observedMaxPrice: max,
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
    return {
      ...card,
      lowestVerifiedOffer: prices?.lowest_verified_offer ?? null,
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
