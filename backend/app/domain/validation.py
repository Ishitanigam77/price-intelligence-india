"""Pure validation/normalization helpers used by domain entities and ORM models.

None of these functions touch the database or a web framework — they operate purely on plain
Python values so they can be unit-tested in isolation and reused later (e.g. from API request
schemas in a future phase).
"""

import re
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.domain.enums import SaleEventSource, SaleEventType
from app.domain.exceptions import (
    InvalidCountryCodeError,
    InvalidCurrencyCodeError,
    InvalidSaleEventError,
    InvalidSlugError,
    InvalidVariantAttributesError,
    NegativeAmountError,
)

_EXTERNAL_SALE_EVENT_SOURCES = frozenset(
    {
        SaleEventSource.OFFICIAL_API,
        SaleEventSource.AFFILIATE_FEED,
        SaleEventSource.PRODUCT_FEED,
        SaleEventSource.OTHER_PERMITTED,
    }
)

_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")
_COUNTRY_PATTERN = re.compile(r"^[A-Z]{2}$")


def validate_slug(value: str) -> str:
    """Validate and return a lowercase-kebab-case slug (e.g. "apple-iphone-16")."""
    if not value or not _SLUG_PATTERN.match(value):
        raise InvalidSlugError(
            f"{value!r} is not a valid slug: expected lowercase letters, digits, and hyphens "
            "only, with no leading/trailing/double hyphens."
        )
    return value


def slugify(value: str) -> str:
    """Derive a valid slug from an arbitrary display string.

    Lowercases, replaces runs of non-alphanumeric characters with a single hyphen, and strips
    leading/trailing hyphens. Raises `InvalidSlugError` if the result is empty.
    """
    lowered = value.strip().lower()
    collapsed = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return validate_slug(collapsed)


def validate_currency_code(value: str) -> str:
    """Validate an ISO 4217 currency code (e.g. "INR")."""
    if not value or not _CURRENCY_PATTERN.match(value):
        raise InvalidCurrencyCodeError(
            f"{value!r} is not a valid ISO 4217 currency code (expected 3 uppercase letters)."
        )
    return value


def validate_country_code(value: str) -> str:
    """Validate an ISO 3166-1 alpha-2 country code (e.g. "IN")."""
    if not value or not _COUNTRY_PATTERN.match(value):
        raise InvalidCountryCodeError(
            f"{value!r} is not a valid ISO 3166-1 alpha-2 country code "
            "(expected 2 uppercase letters)."
        )
    return value


def validate_non_negative_amount(value: Decimal | None, *, field_name: str) -> Decimal | None:
    """Ensure an optional monetary amount is `None` or non-negative (e.g. MRP, fees)."""
    if value is not None and value < 0:
        raise NegativeAmountError(f"{field_name} must not be negative, got {value}.")
    return value


def validate_required_non_negative_amount(value: Decimal | None, *, field_name: str) -> Decimal:
    """Ensure a *required* monetary amount is present and non-negative (e.g. displayed price).

    Unlike `validate_non_negative_amount`, `None` is rejected here rather than passed through —
    a required amount that is missing should fail fast with a clear domain error instead of
    silently reaching the database's NOT NULL constraint.
    """
    if value is None:
        raise NegativeAmountError(f"{field_name} is required and must not be None.")
    if value < 0:
        raise NegativeAmountError(f"{field_name} must not be negative, got {value}.")
    return value


def normalize_variant_attributes(attributes: dict[str, str]) -> dict[str, str]:
    """Normalize a variant's attribute set (e.g. {"Color": " Black "} -> {"color": "black"}).

    Keys and values are lowercased and stripped so that equivalent attribute sets (differing
    only by whitespace or casing) always produce the same normalized form and the same
    `variant_key`.
    """
    if not attributes:
        raise InvalidVariantAttributesError(
            "A product variant must have at least one attribute (e.g. storage, color, size)."
        )
    normalized: dict[str, str] = {}
    for raw_key, raw_value in attributes.items():
        key = str(raw_key).strip().lower()
        value = str(raw_value).strip().lower()
        if not key or not value:
            raise InvalidVariantAttributesError(
                "Product variant attribute keys and values must be non-empty."
            )
        normalized[key] = value
    return normalized


def _require_aware(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise InvalidSaleEventError(f"{field_name} must be timezone-aware.")
    return value


def validate_sale_event_dates(
    start_date: datetime, end_date: datetime
) -> tuple[datetime, datetime]:
    """Require timezone-aware bounds with `end_date` not before `start_date`."""
    start = _require_aware(start_date, field_name="start_date")
    end = _require_aware(end_date, field_name="end_date")
    if end < start:
        raise InvalidSaleEventError("Sale event end_date must not be before start_date.")
    return start, end


def normalize_sale_event_source_ref(source_ref: str | None) -> str | None:
    """Strip provenance text; blank becomes `None` (no invented reference)."""
    if source_ref is None:
        return None
    stripped = source_ref.strip()
    return stripped or None


def validate_sale_event(
    *,
    event_type: SaleEventType,
    source: SaleEventSource,
    source_ref: str | None,
    retailer_id: UUID | None,
    category_id: UUID | None,
    brand_id: UUID | None,
    start_date: datetime,
    end_date: datetime,
) -> str | None:
    """Validate sale-event window, scope, and source provenance.

    Returns the normalized `source_ref`. Does not invent missing retailer/brand/category
    identifiers or fabricate an external source reference.
    """
    validate_sale_event_dates(start_date, end_date)
    ref = normalize_sale_event_source_ref(source_ref)

    if event_type is SaleEventType.RETAILER_SPECIFIC and retailer_id is None:
        raise InvalidSaleEventError("Retailer-specific sale events require retailer_id.")
    if event_type is SaleEventType.BRAND and brand_id is None:
        raise InvalidSaleEventError("Brand sale events require brand_id.")
    if event_type is SaleEventType.CATEGORY and category_id is None:
        raise InvalidSaleEventError("Category sale events require category_id.")

    if (
        event_type is SaleEventType.MANUALLY_CURATED
        and source is not SaleEventSource.MANUAL_CURATION
    ):
        raise InvalidSaleEventError("Manually curated events must use source=manual_curation.")

    if (
        source is SaleEventSource.OBSERVED_PRICE_INFERENCE
        and event_type is SaleEventType.EXTERNALLY_SOURCED
    ):
        raise InvalidSaleEventError(
            "Observed-price inference is calculated from stored observations, "
            "not an externally sourced event."
        )

    if event_type is SaleEventType.EXTERNALLY_SOURCED:
        if source not in _EXTERNAL_SALE_EVENT_SOURCES:
            raise InvalidSaleEventError(
                "Externally sourced events require a legitimate permitted source "
                "(official_api, affiliate_feed, product_feed, or other_permitted)."
            )
        if ref is None:
            raise InvalidSaleEventError(
                "Externally sourced events require source_ref identifying the legitimate source."
            )

    return ref


def build_variant_key(normalized_attributes: dict[str, str]) -> str:
    """Build a deterministic string key from normalized variant attributes.

    Used as part of a uniqueness constraint (`product_id`, `variant_key`) so the same product
    can never have two logically identical variants (e.g. two "128GB / Black" rows).
    """
    return ";".join(f"{key}={value}" for key, value in sorted(normalized_attributes.items()))
