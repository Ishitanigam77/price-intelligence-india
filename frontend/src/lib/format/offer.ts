import { formatMoneyOrUnavailable } from "@/lib/format/money";
import type {
  AdjustmentEligibility,
  AdjustmentKind,
  PriceAdjustmentRead,
  PriceKind,
  RankingCriterion,
  RankingReasonRead,
  SourceType,
} from "@/lib/types/api";

const SOURCE_TYPE_LABELS: Record<SourceType, string> = {
  official_api: "Official retailer listing",
  affiliate_feed: "Partner listing",
  product_feed: "Product listing",
  other_permitted: "Other permitted listing",
};

const PRICE_KIND_LABELS: Record<PriceKind, string> = {
  verified_effective: "Verified price",
  displayed_only: "Listed price",
  estimated_unverified: "Unverified estimate",
};

const ADJUSTMENT_KIND_LABELS: Record<AdjustmentKind, string> = {
  coupon: "Coupon",
  payment_discount: "Payment discount",
  cashback: "Cashback",
  delivery_fee: "Delivery fee",
  platform_fee: "Platform fee",
  displayed_discount: "Listed discount",
  other: "Other adjustment",
};

const ELIGIBILITY_LABELS: Record<AdjustmentEligibility, string> = {
  verified_eligible: "Verified",
  ineligible: "Not eligible",
  unverified: "Not verified",
  unavailable: "Not available",
  membership_only: "Membership only",
  payment_method_specific: "Depends on payment method",
  conditional: "Applies only in some cases",
};

const RANKING_SUMMARY: Record<RankingCriterion, string> = {
  verified_effective_price: "This is the lowest verified price among current offers.",
  displayed_price:
    "This is the lowest listed price among current offers. Extra discounts were not counted because they are not verified.",
  availability: "This offer was chosen because it is currently available.",
  seller_quality: "This offer was chosen based on seller quality among similar prices.",
  delivery: "This offer was chosen based on delivery among similar prices.",
  no_applicable_offer: "No verified offer is available for this variant.",
};

export function formatSourceType(sourceType: SourceType | null | undefined): string {
  if (!sourceType) {
    return "Not provided";
  }
  return SOURCE_TYPE_LABELS[sourceType] ?? "Not provided";
}

export function formatPriceKind(priceKind: PriceKind): string {
  return PRICE_KIND_LABELS[priceKind] ?? "Listed price";
}

export function formatRankingSummary(ranking: RankingReasonRead | null | undefined): string {
  if (!ranking) {
    return "No verified offer is available for this variant.";
  }
  return RANKING_SUMMARY[ranking.criterion] ?? "No verified offer is available for this variant.";
}

export function formatAdjustmentLine(adjustment: PriceAdjustmentRead, currency: string): string {
  const kind = ADJUSTMENT_KIND_LABELS[adjustment.kind] ?? "Price adjustment";
  const eligibility = ELIGIBILITY_LABELS[adjustment.eligibility] ?? "Status unknown";
  const amount =
    adjustment.amount != null ? formatMoneyOrUnavailable(adjustment.amount, currency) : null;
  const effect = adjustment.affects_effective_price
    ? "included in the price you would pay"
    : "not included in the price you would pay";
  const parts = [kind];
  if (amount) {
    parts.push(amount);
  }
  parts.push(eligibility, effect);
  return parts.join(" · ");
}
