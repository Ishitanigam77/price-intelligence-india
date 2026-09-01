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
  extra: Record<string, MoneyAmount | number | string | null>;
}

export interface MonthlyBucketRead {
  month: number;
  month_name: string;
  retailer_id: string | null;
  retailer_slug: string | null;
  retailer_name: string | null;
  years_used: number[];
  observation_count: number;
  minimum: CalculatedMetricRead;
  average: CalculatedMetricRead;
  median: CalculatedMetricRead;
  maximum: CalculatedMetricRead;
  historical_low: CalculatedMetricRead;
  historical_high: CalculatedMetricRead;
  volatility: CalculatedMetricRead;
}

export interface MonthlyPriceIntelligenceRead {
  value_kind: "CALCULATED";
  months: MonthlyBucketRead[];
  retailer_months: MonthlyBucketRead[];
  best_buying_month: MonthlyBucketRead | null;
  best_buying_month_price: CalculatedMetricRead;
  qualifying_observation_count: number;
  calculated_at: string;
  method: string;
  predicted: null;
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
  monthly: MonthlyPriceIntelligenceRead;
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

export type SaleSeverity = "MAJOR" | "ORDINARY" | "UNKNOWN";

export type SaleEvidenceStatus = "confirmed" | "expected" | "inferred" | "unknown";

export type SaleMappingMethod =
  | "fixed_calendar"
  | "festival_relative"
  | "recurring"
  | "retailer_specific"
  | "confirmed_schedule"
  | "insufficient";

export type RecommendationDecision = "BUY_NOW" | "WAIT" | "WATCH" | "INSUFFICIENT_DATA";

export type BuyingWindow =
  | "BUY_NOW"
  | "BUY_IN_ORDINARY_SALE"
  | "WAIT_FOR_MAJOR_SALE"
  | "WAIT"
  | "WATCH"
  | "INSUFFICIENT_DATA";

export type Urgency = "urgent" | "patient";

export type PredictionStatus = "PREDICTED" | "TRAINED" | "INSUFFICIENT_DATA";

export interface ExpectedSaleWindowRead {
  sale_family: string;
  display_name: string;
  sale_type: SaleSeverity;
  evidence_status: SaleEvidenceStatus;
  mapping_method: SaleMappingMethod;
  expected_start_date: string | null;
  expected_end_date: string | null;
  confidence: ConfidenceLevel;
  evidence_count: number;
  historical_years_used: number[];
  retailer_id: string | null;
  occasion_id: string | null;
  duration_days: number | null;
  reason: string;
  predicted: null;
}

export interface RetailerSaleOutlookRead {
  retailer_id: string;
  retailer_slug: string;
  retailer_name: string;
  current_price: MoneyAmount | null;
  current_price_value_kind: ValueKind | null;
  availability: AvailabilityStatus | null;
  is_current_cheapest: boolean;
  expected_sale_price: MoneyAmount | null;
  expected_sale_price_value_kind: ValueKind | null;
  predicted_sale_price: MoneyAmount | null;
  predicted_lower_bound: MoneyAmount | null;
  predicted_upper_bound: MoneyAmount | null;
  predicted_confidence: number | null;
  historical_sale_price: MoneyAmount | null;
  historical_occurrence_count: number;
  expected_saving: MoneyAmount | null;
  expected_saving_percentage: MoneyAmount | null;
  expected_saving_value_kind: ValueKind | null;
  confidence: ConfidenceLevel | null;
  reliability: ConfidenceLevel | null;
  status: MetricStatus;
  insufficient_reason: string | null;
}

export interface SaleOpportunityRead {
  sale_type: SaleSeverity;
  window: ExpectedSaleWindowRead;
  expected_price: MoneyAmount | null;
  expected_price_value_kind: ValueKind | null;
  expected_saving: MoneyAmount | null;
  expected_saving_percentage: MoneyAmount | null;
  expected_saving_value_kind: ValueKind | null;
  days_until_start: number | null;
  likely_best_retailer_id: string | null;
  likely_best_retailer_slug: string | null;
  likely_best_retailer_name: string | null;
  retailer_outlooks: RetailerSaleOutlookRead[];
  confidence: ConfidenceLevel | null;
  historical_reliability: ConfidenceLevel | null;
  status: MetricStatus;
  insufficient_reason: string | null;
}

export interface VariantSaleIntelligenceRead {
  product_id: string;
  product_variant_id: string;
  variant_key: string | null;
  current_cheapest_retailer_id: string | null;
  current_cheapest_retailer_slug: string | null;
  current_cheapest_retailer_name: string | null;
  current_cheapest_price: MoneyAmount | null;
  current_effective_price: MoneyAmount | null;
  current_availability: AvailabilityStatus | null;
  calendar: ExpectedSaleWindowRead[];
  ordinary: SaleOpportunityRead | null;
  major: SaleOpportunityRead | null;
  expected_best_retailer: RetailerSaleOutlookRead | null;
  disclaimer: string;
  calculated_at: string;
  predicted: null;
}

export interface ProductSaleIntelligenceRead {
  product_id: string;
  as_of: string;
  disclaimer: string;
  variants: VariantSaleIntelligenceRead[];
  predicted: null;
}

export interface OpportunitySnapshotRead {
  sale_type: string;
  display_name: string | null;
  evidence_status: string | null;
  expected_start_date: string | null;
  expected_end_date: string | null;
  days_until_start: number | null;
  expected_price: MoneyAmount | null;
  expected_price_value_kind: ValueKind | null;
  expected_saving: MoneyAmount | null;
  expected_saving_percentage: MoneyAmount | null;
  expected_saving_value_kind: "CALCULATED" | null;
  likely_best_retailer_name: string | null;
  confidence: number | null;
  historical_reliability: string | null;
  status: string | null;
}

export interface VariantRecommendationRead {
  product_variant_id: string;
  recommendation: RecommendationDecision;
  expected_saving: MoneyAmount | null;
  expected_saving_percentage: MoneyAmount | null;
  confidence: number | null;
  reasons: string[];
  triggered_rule_ids: string[];
  disclaimer: string;
  prediction_used: boolean;
  insufficient: string | null;
  provenance: {
    current_price_value_kind: ValueKind | null;
    historical_value_kind: "CALCULATED";
    predicted_value_kind: "PREDICTED" | null;
    expected_saving_value_kind: "CALCULATED" | null;
    expected_saving_basis: string | null;
  };
  evidence: {
    current_effective_price: MoneyAmount | null;
    historical_percentile: MoneyAmount | null;
    historical_low: MoneyAmount | null;
    average_30d: MoneyAmount | null;
    average_90d: MoneyAmount | null;
    trend_direction: TrendDirection | null;
    predicted_sale_price: MoneyAmount | null;
    prediction_confidence: number | null;
    prediction_used: boolean;
    upcoming_sale_name: string | null;
    upcoming_sale_days: number | null;
    freshness_status: FreshnessStatus;
    qualifying_observation_count: number;
    expected_saving_basis: string | null;
    urgency: Urgency | null;
    buying_window: BuyingWindow | null;
    ordinary_sale_name: string | null;
    ordinary_sale_days: number | null;
    major_sale_name: string | null;
    major_sale_days: number | null;
  };
  buying_window: BuyingWindow | null;
  urgency: Urgency | null;
  ordinary_opportunity: OpportunitySnapshotRead | null;
  major_opportunity: OpportunitySnapshotRead | null;
}

export interface ProductRecommendationRead {
  product_id: string;
  as_of: string;
  disclaimer: string;
  phase10_status: string | null;
  phase10_model_version: string | null;
  variants: VariantRecommendationRead[];
}

export interface InsufficientDataRead {
  code: string;
  reason: string;
}

export interface SalePricePredictionRead {
  value_kind: "PREDICTED";
  is_prediction: true;
  disclaimer: string;
  status: PredictionStatus;
  predicted_price: MoneyAmount | null;
  lower_bound: MoneyAmount | null;
  upper_bound: MoneyAmount | null;
  confidence: number | null;
  model_version: string | null;
  training_data_size: number | null;
  currency: string;
  as_of: string;
  product_id: string | null;
  product_variant_id: string | null;
  retailer_id: string | null;
  seller_id: string | null;
  feature_version: string | null;
  insufficient: InsufficientDataRead | null;
  uncertainty_method: string | null;
}

export interface ProductSalePricePredictionRead {
  product_id: string;
  as_of: string;
  value_kind: "PREDICTED";
  is_prediction: true;
  disclaimer: string;
  status: PredictionStatus;
  model_version: string | null;
  training_data_size: number | null;
  feature_version: string | null;
  predictions: SalePricePredictionRead[];
  insufficient: InsufficientDataRead | null;
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
