"""Price comparison engine.

For each matched product variant, compares retailer offers and selects the best *verified*
price using deterministic, explainable rules. Never uses ML. Never applies unverified
coupons, generic cashback, payment-method discounts without eligibility, membership-only
benefits, or assumed delivery charges to `effective_price`.
"""

from app.pricing.config import PricingConfig, get_pricing_config
from app.pricing.engine import PriceComparisonEngine
from app.pricing.enums import (
    FreshnessStatus,
    InsufficientReasonCode,
    MetricStatus,
    PriceKind,
    RankingCriterion,
    TrendDirection,
    ValueKind,
)
from app.pricing.history import PriceHistoryEngine
from app.pricing.models import (
    ComparedOffer,
    DataFreshness,
    OfferInput,
    PriceAdjustment,
    ProductComparison,
    RankingExplanation,
    SellerSnapshot,
    VariantComparison,
)

__all__ = [
    "ComparedOffer",
    "DataFreshness",
    "FreshnessStatus",
    "InsufficientReasonCode",
    "MetricStatus",
    "OfferInput",
    "PriceAdjustment",
    "PriceComparisonEngine",
    "PriceHistoryEngine",
    "PriceKind",
    "PricingConfig",
    "ProductComparison",
    "RankingCriterion",
    "RankingExplanation",
    "SellerSnapshot",
    "TrendDirection",
    "ValueKind",
    "VariantComparison",
    "get_pricing_config",
]
