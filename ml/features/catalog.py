"""Feature catalog (names, versions) shared by training and inference."""

from ml.config import FEATURE_VERSION

NUMERIC_FEATURES: tuple[str, ...] = (
    "current_price",
    "avg_7d",
    "avg_30d",
    "avg_90d",
    "historical_low",
    "historical_high",
    "price_volatility",
    "previous_sale_price",
    "previous_sale_low",
    "previous_sale_count",
    "mrp",
    "days_until_sale",
    "month",
    "day_of_week",
    "day_of_year",
    "is_weekend",
)

CATEGORICAL_FEATURES: tuple[str, ...] = (
    "retailer_id",
    "seller_id",
    "brand_id",
    "category_id",
    "sale_event_id",
    "sale_event_type",
)

FEATURE_NAMES: tuple[str, ...] = NUMERIC_FEATURES + tuple(
    f"cat_{name}" for name in CATEGORICAL_FEATURES
)

ALWAYS_AVAILABLE_NUMERIC = frozenset(
    {"previous_sale_count", "month", "day_of_week", "day_of_year", "is_weekend"}
)


def encoded_feature_name(categorical: str) -> str:
    return f"cat_{categorical}"


__all__ = [
    "ALWAYS_AVAILABLE_NUMERIC",
    "CATEGORICAL_FEATURES",
    "FEATURE_NAMES",
    "FEATURE_VERSION",
    "NUMERIC_FEATURES",
    "encoded_feature_name",
]
