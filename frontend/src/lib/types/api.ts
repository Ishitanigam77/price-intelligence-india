/**
 * TypeScript types matching FastAPI / Pydantic response schemas.
 * Field names and optionality follow the backend contracts exactly.
 * Decimal values may arrive as strings or numbers depending on JSON encoding.
 */

export type MoneyAmount = string | number;

export type AvailabilityStatus = "in_stock" | "out_of_stock" | "limited_stock" | "unknown";

export type SourceType = "official_api" | "affiliate_feed" | "product_feed" | "other_permitted";

export type ConfidenceLevel = "high" | "medium" | "low";

export type AdjustmentKind =
  | "coupon"
  | "payment_discount"
  | "cashback"
  | "delivery_fee"
  | "platform_fee"
  | "displayed_discount"
  | "other";

export type AdjustmentEligibility =
  | "verified_eligible"
  | "ineligible"
  | "unverified"
  | "unavailable"
  | "membership_only"
  | "payment_method_specific"
  | "conditional";

export type PriceKind = "verified_effective" | "displayed_only" | "estimated_unverified";

export type FreshnessStatus = "fresh" | "aging" | "stale" | "missing";

export type RankingCriterion =
  | "verified_effective_price"
  | "displayed_price"
  | "availability"
  | "seller_quality"
  | "delivery"
  | "no_applicable_offer";

export type ValueKind = "OBSERVED" | "CALCULATED" | "PREDICTED";

export type MetricStatus = "available" | "insufficient_history";

export type InsufficientReasonCode =
  | "no_qualifying_observations"
  | "no_observations_in_window"
  | "below_minimum_observation_count"
  | "no_current_price"
  | "no_comparison_baseline"
  | "zero_time_span"
  | "zero_baseline_price";

export type TrendDirection = "rising" | "falling" | "stable" | "insufficient_history";

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface ErrorDetail {
  code: string;
  message: string;
  fields?: Record<string, unknown>[] | null;
}

export interface ErrorResponse {
  error: ErrorDetail;
}

export interface BrandRead {
  id: string;
  name: string;
  slug: string;
  website_url: string | null;
  is_active: boolean;
}

export interface CategoryRead {
  id: string;
  name: string;
  slug: string;
  parent_id: string | null;
  is_active: boolean;
}

export interface ProductRead {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  brand_id: string | null;
  category_id: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProductVariantRead {
  id: string;
  product_id: string;
  name: string | null;
  attributes: Record<string, string>;
  variant_key: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface RetailerRead {
  id: string;
  name: string;
  slug: string;
  website_url: string | null;
  country_code: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SellerRead {
  id: string;
  retailer_id: string;
  name: string;
  external_seller_id: string | null;
  is_first_party: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PriceSnapshotRead {
  id: string;
  retailer_product_id: string;
  seller_id: string | null;
  observed_at: string;
  currency: string;
  mrp: MoneyAmount | null;
  displayed_price: MoneyAmount;
  effective_price: MoneyAmount | null;
  delivery_fee: MoneyAmount | null;
  platform_fee: MoneyAmount | null;
  availability: AvailabilityStatus;
  source_type: SourceType;
  source_url: string | null;
  confidence: ConfidenceLevel;
  created_at: string;
}

export interface RetailerSearchFailure {
  retailer_id: string;
  error_code: string;
  message: string;
}

export interface ProductSearchHit {
  product: ProductRead;
  variant: ProductVariantRead;
  retailer: RetailerRead;
  seller: SellerRead | null;
  retailer_product_id: string;
  retailer_sku: string;
  displayed_price: MoneyAmount;
  mrp: MoneyAmount | null;
  effective_price: MoneyAmount | null;
  currency: string;
  availability: AvailabilityStatus;
  source_url: string | null;
  observed_at: string;
  source_type: SourceType;
  confidence: ConfidenceLevel;
}

export interface ProductSearchPage extends Page<ProductSearchHit> {
  query: string;
  failures: RetailerSearchFailure[];
  consulted_retailer_ids: string[];
}

export interface PriceAdjustmentRead {
  kind: AdjustmentKind;
  amount: MoneyAmount | null;
  source: string;
  eligibility: AdjustmentEligibility;
  observed_at: string | null;
  confidence: ConfidenceLevel;
  affects_effective_price: boolean;
}

export interface OfferSellerRead {
  seller_id: string | null;
  name: string | null;
  is_first_party: boolean | null;
  is_active: boolean | null;
  quality_score: number;
}

export interface DataFreshnessRead {
  status: FreshnessStatus;
  as_of: string;
  observed_at: string | null;
  age_seconds: number | null;
  oldest_observation: string | null;
  newest_observation: string | null;
  stale_offer_count: number;
  missing_observation_count: number;
  offer_count: number;
}

export interface RankingReasonRead {
  criterion: RankingCriterion;
  reason: string;
  tie_breakers_applied: RankingCriterion[];
  selected_offer_id: string | null;
}

export interface ComparedOfferRead {
  offer_id: string;
  variant_id: string;
  retailer_id: string;
  retailer_slug: string;
  retailer_name: string;
  retailer_product_id: string;
  seller: OfferSellerRead;
  displayed_price: MoneyAmount | null;
  mrp: MoneyAmount | null;
  discount_percentage: MoneyAmount | null;
  coupon_discount: MoneyAmount | null;
  payment_discount: MoneyAmount | null;
  cashback: MoneyAmount | null;
  delivery_fee: MoneyAmount | null;
  platform_fee: MoneyAmount | null;
  effective_price: MoneyAmount | null;
  unverified_estimated_price: MoneyAmount | null;
  unverified_price_kind: PriceKind | null;
  source_effective_price: MoneyAmount | null;
  price_kind: PriceKind;
  availability: AvailabilityStatus;
  source_url: string | null;
  source_type: SourceType | null;
  observation_timestamp: string | null;
  confidence: ConfidenceLevel;
  observation_confidence: ConfidenceLevel | null;
  freshness: DataFreshnessRead;
  adjustments: PriceAdjustmentRead[];
  currency: string;
  rank: number;
  is_available: boolean;
  can_win_verified_ranking: boolean;
}

export interface VariantPricesRead {
  variant_id: string;
  variant_key: string | null;
  offers: ComparedOfferRead[];
  lowest_verified_offer: ComparedOfferRead | null;
  ranking_reason: RankingReasonRead;
  data_freshness: DataFreshnessRead;
}

export interface ProductPricesRead {
  product_id: string;
  variants: VariantPricesRead[];
  lowest_verified_offer: ComparedOfferRead | null;
  ranking_reason: RankingReasonRead | null;
  data_freshness: DataFreshnessRead;
  as_of: string;
}

export interface InsufficientHistoryRead {
  code: InsufficientReasonCode;
  reason: string;
}

export interface CalculatedMetricRead {
  value_kind: "CALCULATED";
  status: MetricStatus;
  value: MoneyAmount | null;
  unit: string;
  window_days: number | null;
  observation_count: number;
  calculated_at: string;
  insufficient: InsufficientHistoryRead | null;
  extra: Record<string, MoneyAmount | string | null>;
}

export interface ExtremaMetricRead extends CalculatedMetricRead {
  snapshot_id: string | null;
  observed_at: string | null;
  retailer_id: string | null;
  seller_id: string | null;
  source_url: string | null;
}

export interface PriceDropRead {
  value_kind: "CALCULATED";
  status: MetricStatus;
  drop_occurred: boolean | null;
  percentage_change: MoneyAmount | null;
  current_price: MoneyAmount | null;
  baseline_price: MoneyAmount | null;
  current_observed_at: string | null;
  baseline_observed_at: string | null;
  current_snapshot_id: string | null;
  baseline_snapshot_id: string | null;
  baseline_retailer_id: string | null;
  baseline_seller_id: string | null;
  baseline_description: string;
  observation_count: number;
  calculated_at: string;
  insufficient: InsufficientHistoryRead | null;
}

export interface TrendRead {
  value_kind: "CALCULATED";
  status: MetricStatus;
  direction: TrendDirection;
  implied_percent_change: MoneyAmount | null;
  slope_per_day: MoneyAmount | null;
  method: string;
  observation_count: number;
  first_observed_at: string | null;
  last_observed_at: string | null;
  calculated_at: string;
  insufficient: InsufficientHistoryRead | null;
}

export interface HistoryProvenanceRead {
  observations_value_kind: "OBSERVED";
  calculations_value_kind: "CALCULATED";
  predicted: null;
  predicted_value_kind: null;
  analysis_price_rule: string;
  price_drop_baseline: string;
  trend_method: string;
}

export interface HistoryObservationRead {
  value_kind: "OBSERVED";
  id: string;
  product_id: string;
  product_variant_id: string;
  retailer_id: string;
  retailer_slug: string;
  retailer_name: string;
  retailer_product_id: string;
  seller_id: string | null;
  source_url: string | null;
  source_type: SourceType;
  observed_at: string;
  created_at: string;
  currency: string;
  displayed_price: MoneyAmount;
  effective_price: MoneyAmount | null;
  effective_price_value_kind: "CALCULATED" | null;
  mrp: MoneyAmount | null;
  analysis_price: MoneyAmount;
  analysis_price_field: "effective_price" | "displayed_price";
  availability: AvailabilityStatus;
  confidence: ConfidenceLevel;
  qualifies_for_calculations: boolean;
}

export interface VariantHistoryRead {
  product_id: string;
  product_variant_id: string;
  variant_key: string | null;
  observations: Page<HistoryObservationRead>;
  qualifying_observation_count: number;
  excluded_unverified_observation_count: number;
  current_observation: HistoryObservationRead | null;
  average_7d: CalculatedMetricRead;
  average_30d: CalculatedMetricRead;
  average_90d: CalculatedMetricRead;
  average_180d: CalculatedMetricRead;
  historical_low: ExtremaMetricRead;
  historical_high: ExtremaMetricRead;
  current_price_percentile: CalculatedMetricRead;
  volatility: CalculatedMetricRead;
  percentage_change: CalculatedMetricRead;
  price_drop: PriceDropRead;
  trend: TrendRead;
  data_freshness: DataFreshnessRead;
  provenance: HistoryProvenanceRead;
  calculated_at: string;
}

export interface ProductHistoryRead {
  product_id: string;
  variants: VariantHistoryRead[];
  data_freshness: DataFreshnessRead;
  provenance: HistoryProvenanceRead;
  calculated_at: string;
  predicted: null;
}

/** Placeholder deal schema. The backend currently always returns an empty page. */
export type DealRead = Record<string, never>;

export interface LivenessResponse {
  status: "ok";
}

export interface PaginationQuery {
  limit?: number;
  offset?: number;
}

export interface SearchProductsQuery extends PaginationQuery {
  q: string;
  category?: string;
}

export interface ProductHistoryQuery extends PaginationQuery {
  variant_id?: string;
  since?: string;
  until?: string;
}

export interface ListRetailersQuery extends PaginationQuery {
  active_only?: boolean;
}

export interface PreferenceRead {
  email_alerts_enabled: boolean;
  default_currency: string;
}

export interface UserProfileRead {
  id: string;
  clerk_user_id: string;
  email: string | null;
  display_name: string | null;
  preferences: PreferenceRead;
  created_at: string;
  updated_at: string;
}

export interface UserProfileUpdate {
  display_name?: string | null;
  preferences?: {
    email_alerts_enabled?: boolean;
    default_currency?: string;
  };
}

export interface WatchlistRead {
  id: string;
  product_id: string;
  product: ProductRead | null;
  created_at: string;
  updated_at: string;
}

export interface SavedProductItemRead {
  id: string;
  product_id: string;
  product: ProductRead | null;
  created_at: string;
  updated_at: string;
}

export interface TargetPriceRead {
  id: string;
  product_id: string;
  amount: MoneyAmount;
  currency: string;
  product: ProductRead | null;
  created_at: string;
  updated_at: string;
}

export interface AlertRead {
  id: string;
  product_id: string;
  threshold_amount: MoneyAmount;
  currency: string;
  is_enabled: boolean;
  product: ProductRead | null;
  created_at: string;
  updated_at: string;
}
