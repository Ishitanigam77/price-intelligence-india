"""Unit tests for `app.domain.validation` — pure functions, no database involved."""

from decimal import Decimal

import pytest

from app.domain.exceptions import (
    InvalidCountryCodeError,
    InvalidCurrencyCodeError,
    InvalidSlugError,
    InvalidVariantAttributesError,
    NegativeAmountError,
)
from app.domain.validation import (
    build_variant_key,
    normalize_variant_attributes,
    slugify,
    validate_country_code,
    validate_currency_code,
    validate_non_negative_amount,
    validate_slug,
)


class TestValidateSlug:
    @pytest.mark.parametrize("value", ["apple-iphone-16", "a", "a1-b2", "boat-airdopes-141"])
    def test_accepts_valid_slugs(self, value: str) -> None:
        assert validate_slug(value) == value

    @pytest.mark.parametrize(
        "value",
        ["", "Apple-iPhone", "apple_iphone", "-apple", "apple-", "apple--iphone", "apple iphone"],
    )
    def test_rejects_invalid_slugs(self, value: str) -> None:
        with pytest.raises(InvalidSlugError):
            validate_slug(value)


class TestSlugify:
    def test_derives_slug_from_display_name(self) -> None:
        assert slugify("Apple iPhone 16 (128GB)") == "apple-iphone-16-128gb"

    def test_collapses_repeated_separators(self) -> None:
        assert slugify("boAt   Airdopes -- 141") == "boat-airdopes-141"

    def test_raises_when_nothing_left_after_slugifying(self) -> None:
        with pytest.raises(InvalidSlugError):
            slugify("***")


class TestValidateCurrencyCode:
    def test_accepts_inr(self) -> None:
        assert validate_currency_code("INR") == "INR"

    @pytest.mark.parametrize("value", ["inr", "IN", "INRR", "", "123"])
    def test_rejects_malformed_codes(self, value: str) -> None:
        with pytest.raises(InvalidCurrencyCodeError):
            validate_currency_code(value)


class TestValidateCountryCode:
    def test_accepts_in(self) -> None:
        assert validate_country_code("IN") == "IN"

    @pytest.mark.parametrize("value", ["in", "IND", "", "1N"])
    def test_rejects_malformed_codes(self, value: str) -> None:
        with pytest.raises(InvalidCountryCodeError):
            validate_country_code(value)


class TestValidateNonNegativeAmount:
    def test_allows_none(self) -> None:
        assert validate_non_negative_amount(None, field_name="mrp") is None

    def test_allows_zero_and_positive(self) -> None:
        assert validate_non_negative_amount(Decimal("0"), field_name="mrp") == Decimal("0")
        assert validate_non_negative_amount(Decimal("10.50"), field_name="mrp") == Decimal("10.50")

    def test_rejects_negative(self) -> None:
        with pytest.raises(NegativeAmountError):
            validate_non_negative_amount(Decimal("-1"), field_name="mrp")


class TestNormalizeVariantAttributes:
    def test_normalizes_case_and_whitespace(self) -> None:
        result = normalize_variant_attributes({" Color ": " Black ", "Storage": "128GB"})
        assert result == {"color": "black", "storage": "128gb"}

    def test_rejects_empty_attributes(self) -> None:
        with pytest.raises(InvalidVariantAttributesError):
            normalize_variant_attributes({})

    @pytest.mark.parametrize("attributes", [{"": "black"}, {"color": ""}, {"  ": "  "}])
    def test_rejects_blank_keys_or_values(self, attributes: dict[str, str]) -> None:
        with pytest.raises(InvalidVariantAttributesError):
            normalize_variant_attributes(attributes)


class TestBuildVariantKey:
    def test_is_deterministic_regardless_of_input_order(self) -> None:
        key_a = build_variant_key({"color": "black", "storage": "128gb"})
        key_b = build_variant_key({"storage": "128gb", "color": "black"})
        assert key_a == key_b == "color=black;storage=128gb"

    def test_different_attributes_produce_different_keys(self) -> None:
        key_a = build_variant_key({"color": "black", "storage": "128gb"})
        key_b = build_variant_key({"color": "black", "storage": "256gb"})
        assert key_a != key_b
