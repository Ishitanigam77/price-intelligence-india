import type {
  ComparedOfferRead,
  DataFreshnessRead,
  HistoryObservationRead,
  ProductHistoryRead,
  ProductPricesRead,
  ProductRead,
  ProductSearchHit,
  ProductSearchPage,
  ProductVariantRead,
  RetailerRead,
  VariantHistoryRead,
} from "@/lib/types/api";

/** Clearly labelled fixture data for frontend tests. Not real retailer prices. */

export const FIXTURE_NOW = "2026-08-27T12:00:00+00:00";

export const freshnessFresh: DataFreshnessRead = {
  status: "fresh",
  as_of: FIXTURE_NOW,
  observed_at: FIXTURE_NOW,
  age_seconds: 120,
  oldest_observation: FIXTURE_NOW,
  newest_observation: FIXTURE_NOW,
  stale_offer_count: 0,
  missing_observation_count: 0,
  offer_count: 1,
};

export const productFixture: ProductRead = {
  id: "11111111-1111-1111-1111-111111111111",
  name: "Fictional Orchard Aurora 5G Smartphone",
  slug: "fictional-orchard-aurora-5g",
  description: "Fixture product used only in frontend tests.",
  brand_id: null,
  category_id: null,
  is_active: true,
  created_at: FIXTURE_NOW,
  updated_at: FIXTURE_NOW,
};

export const variantFixture: ProductVariantRead = {
  id: "22222222-2222-2222-2222-222222222222",
  product_id: productFixture.id,
  name: "128 GB · Midnight",
  attributes: { storage: "128 GB", colour: "Midnight" },
  variant_key: "colour=midnight|storage=128gb",
  is_active: true,
  created_at: FIXTURE_NOW,
  updated_at: FIXTURE_NOW,
};

export const retailerFixture: RetailerRead = {
  id: "33333333-3333-3333-3333-333333333333",
  name: "Fictional Mock Mart A",
  slug: "mock-retailer-a",
  website_url: "https://mock-retailer-a.example.test",
  country_code: "IN",
  is_active: true,
  created_at: FIXTURE_NOW,
  updated_at: FIXTURE_NOW,
};

export const searchHitFixture: ProductSearchHit = {
  product: productFixture,
  variant: variantFixture,
  retailer: retailerFixture,
  seller: {
    id: "44444444-4444-4444-4444-444444444444",
    retailer_id: retailerFixture.id,
    name: "Fictional Mock Mart A",
    external_seller_id: "A-SELLER-0",
    is_first_party: true,
    is_active: true,
    created_at: FIXTURE_NOW,
    updated_at: FIXTURE_NOW,
  },
  retailer_product_id: "55555555-5555-5555-5555-555555555555",
  retailer_sku: "A-MOB-1001",
  displayed_price: "59999.00",
  mrp: "69999.00",
  effective_price: null,
  currency: "INR",
  availability: "in_stock",
  source_url: "https://mock-retailer-a.example.test/A-MOB-1001",
  observed_at: FIXTURE_NOW,
  source_type: "official_api",
  confidence: "high",
};

export function searchPageFixture(
  items: ProductSearchHit[] = [searchHitFixture],
): ProductSearchPage {
  return {
    items,
    total: items.length,
    limit: 50,
    offset: 0,
    query: "aurora",
    failures: [],
    consulted_retailer_ids: ["mock-retailer-a"],
  };
}

export const offerFixture: ComparedOfferRead = {
  offer_id: "66666666-6666-6666-6666-666666666666",
  variant_id: variantFixture.id,
  retailer_id: retailerFixture.id,
  retailer_slug: retailerFixture.slug,
  retailer_name: retailerFixture.name,
  retailer_product_id: searchHitFixture.retailer_product_id,
  seller: {
    seller_id: searchHitFixture.seller?.id ?? null,
    name: "Fictional Mock Mart A",
    is_first_party: true,
    is_active: true,
    quality_score: 80,
  },
  displayed_price: "59999.00",
  mrp: "69999.00",
  discount_percentage: null,
  coupon_discount: null,
  payment_discount: null,
  cashback: null,
  delivery_fee: null,
  platform_fee: null,
  effective_price: "59999.00",
  unverified_estimated_price: null,
  unverified_price_kind: null,
  source_effective_price: null,
  price_kind: "verified_effective",
  availability: "in_stock",
  source_url: searchHitFixture.source_url,
  source_type: "official_api",
  observation_timestamp: FIXTURE_NOW,
  confidence: "high",
  observation_confidence: "high",
  freshness: freshnessFresh,
  adjustments: [],
  currency: "INR",
  rank: 1,
  is_available: true,
  can_win_verified_ranking: true,
};

export const pricesFixture: ProductPricesRead = {
  product_id: productFixture.id,
  variants: [
    {
      variant_id: variantFixture.id,
      variant_key: variantFixture.variant_key,
      offers: [offerFixture],
      lowest_verified_offer: offerFixture,
      ranking_reason: {
        criterion: "verified_effective_price",
        reason: "Lowest verified effective price among in-stock fixture offers.",
        tie_breakers_applied: [],
        selected_offer_id: offerFixture.offer_id,
      },
      data_freshness: freshnessFresh,
    },
  ],
  lowest_verified_offer: offerFixture,
  ranking_reason: {
    criterion: "verified_effective_price",
    reason: "Lowest verified effective price among in-stock fixture offers.",
    tie_breakers_applied: [],
    selected_offer_id: offerFixture.offer_id,
  },
  data_freshness: freshnessFresh,
  as_of: FIXTURE_NOW,
};

function metric(value: string, status: "available" | "insufficient_history" = "available") {
  return {
    value_kind: "CALCULATED" as const,
    status,
    value: status === "available" ? value : null,
    unit: "INR",
    window_days: 7,
    observation_count: status === "available" ? 4 : 0,
    calculated_at: FIXTURE_NOW,
    insufficient:
      status === "insufficient_history"
        ? { code: "no_qualifying_observations" as const, reason: "No qualifying observations." }
        : null,
    extra: {},
  };
}

export const observationFixture = (
  overrides: Partial<HistoryObservationRead> = {},
): HistoryObservationRead => ({
  value_kind: "OBSERVED",
  id: "77777777-7777-7777-7777-777777777777",
  product_id: productFixture.id,
  product_variant_id: variantFixture.id,
  retailer_id: retailerFixture.id,
  retailer_slug: retailerFixture.slug,
  retailer_name: retailerFixture.name,
  retailer_product_id: searchHitFixture.retailer_product_id,
  seller_id: searchHitFixture.seller?.id ?? null,
  source_url: searchHitFixture.source_url,
  source_type: "official_api",
  observed_at: FIXTURE_NOW,
  created_at: FIXTURE_NOW,
  currency: "INR",
  displayed_price: "59999.00",
  effective_price: "59999.00",
  effective_price_value_kind: "CALCULATED",
  mrp: "69999.00",
  analysis_price: "59999.00",
  analysis_price_field: "displayed_price",
  availability: "in_stock",
  confidence: "high",
  qualifies_for_calculations: true,
  ...overrides,
});

export const variantHistoryFixture: VariantHistoryRead = {
  product_id: productFixture.id,
  product_variant_id: variantFixture.id,
  variant_key: variantFixture.variant_key,
  observations: {
    items: [
      observationFixture({
        id: "aaaaaaa1-aaaa-aaaa-aaaa-aaaaaaaaaaa1",
        observed_at: "2026-08-20T12:00:00+00:00",
        displayed_price: "62000.00",
        analysis_price: "62000.00",
      }),
      observationFixture({
        id: "aaaaaaa2-aaaa-aaaa-aaaa-aaaaaaaaaaa2",
        observed_at: "2026-08-27T12:00:00+00:00",
        displayed_price: "59999.00",
        analysis_price: "59999.00",
      }),
    ],
    total: 2,
    limit: 200,
    offset: 0,
  },
  qualifying_observation_count: 2,
  excluded_unverified_observation_count: 0,
  current_observation: observationFixture(),
  average_7d: metric("61000.00"),
  average_30d: metric("61000.00"),
  average_90d: metric("61000.00"),
  average_180d: metric("61000.00"),
  historical_low: {
    ...metric("59999.00"),
    snapshot_id: null,
    observed_at: FIXTURE_NOW,
    retailer_id: retailerFixture.id,
    seller_id: null,
    source_url: null,
  },
  historical_high: {
    ...metric("62000.00"),
    snapshot_id: null,
    observed_at: FIXTURE_NOW,
    retailer_id: retailerFixture.id,
    seller_id: null,
    source_url: null,
  },
  current_price_percentile: { ...metric("0"), unit: "percentile" },
  volatility: { ...metric("0.02"), unit: "ratio" },
  percentage_change: { ...metric("-3.23"), unit: "percent" },
  price_drop: {
    value_kind: "CALCULATED",
    status: "available",
    drop_occurred: true,
    percentage_change: "-3.23",
    current_price: "59999.00",
    baseline_price: "62000.00",
    current_observed_at: FIXTURE_NOW,
    baseline_observed_at: "2026-08-20T12:00:00+00:00",
    current_snapshot_id: null,
    baseline_snapshot_id: null,
    baseline_retailer_id: retailerFixture.id,
    baseline_seller_id: null,
    baseline_description: "previous qualifying observation on the same retailer listing",
    observation_count: 2,
    calculated_at: FIXTURE_NOW,
    insufficient: null,
  },
  trend: {
    value_kind: "CALCULATED",
    status: "available",
    direction: "falling",
    implied_percent_change: "-3.23",
    slope_per_day: "-286.00",
    method: "linear_regression",
    observation_count: 2,
    first_observed_at: "2026-08-20T12:00:00+00:00",
    last_observed_at: FIXTURE_NOW,
    calculated_at: FIXTURE_NOW,
    insufficient: null,
  },
  data_freshness: freshnessFresh,
  provenance: {
    observations_value_kind: "OBSERVED",
    calculations_value_kind: "CALCULATED",
    predicted: null,
    predicted_value_kind: null,
    analysis_price_rule: "verified_effective_else_displayed",
    price_drop_baseline: "previous_qualifying_observation",
    trend_method: "linear_regression",
  },
  calculated_at: FIXTURE_NOW,
};

export const historyFixture: ProductHistoryRead = {
  product_id: productFixture.id,
  variants: [variantHistoryFixture],
  data_freshness: freshnessFresh,
  provenance: variantHistoryFixture.provenance,
  calculated_at: FIXTURE_NOW,
  predicted: null,
};

export const insufficientHistoryFixture: ProductHistoryRead = {
  product_id: productFixture.id,
  variants: [
    {
      ...variantHistoryFixture,
      observations: { items: [], total: 0, limit: 200, offset: 0 },
      qualifying_observation_count: 0,
      current_observation: null,
      average_7d: metric("0", "insufficient_history"),
      average_30d: metric("0", "insufficient_history"),
      average_90d: metric("0", "insufficient_history"),
      average_180d: metric("0", "insufficient_history"),
      historical_low: {
        ...metric("0", "insufficient_history"),
        snapshot_id: null,
        observed_at: null,
        retailer_id: null,
        seller_id: null,
        source_url: null,
      },
      historical_high: {
        ...metric("0", "insufficient_history"),
        snapshot_id: null,
        observed_at: null,
        retailer_id: null,
        seller_id: null,
        source_url: null,
      },
      current_price_percentile: metric("0", "insufficient_history"),
      volatility: metric("0", "insufficient_history"),
      percentage_change: metric("0", "insufficient_history"),
      trend: {
        ...variantHistoryFixture.trend,
        status: "insufficient_history",
        direction: "insufficient_history",
        insufficient: {
          code: "no_qualifying_observations",
          reason: "No qualifying observations.",
        },
      },
      data_freshness: {
        ...freshnessFresh,
        status: "missing",
        observed_at: null,
        newest_observation: null,
        oldest_observation: null,
        offer_count: 0,
      },
    },
  ],
  data_freshness: {
    ...freshnessFresh,
    status: "missing",
    observed_at: null,
    newest_observation: null,
  },
  provenance: variantHistoryFixture.provenance,
  calculated_at: FIXTURE_NOW,
  predicted: null,
};
