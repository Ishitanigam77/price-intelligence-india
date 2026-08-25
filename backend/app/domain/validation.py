"""Pure validation/normalization helpers used by domain entities and ORM models.

None of these functions touch the database or a web framework — they operate purely on plain
Python values so they can be unit-tested in isolation and reused later (e.g. from API request
schemas in a future phase).
"""

import re
from decimal import Decimal

from app.domain.exceptions import (
    InvalidCountryCodeError,
    InvalidCurrencyCodeError,
    InvalidSlugError,
    InvalidVariantAttributesError,
    NegativeAmountError,
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


def build_variant_key(normalized_attributes: dict[str, str]) -> str:
    """Build a deterministic string key from normalized variant attributes.

    Used as part of a uniqueness constraint (`product_id`, `variant_key`) so the same product
    can never have two logically identical variants (e.g. two "128GB / Black" rows).
    """
    return ";".join(f"{key}={value}" for key, value in sorted(normalized_attributes.items()))
