"""Tests for the standardized adapter models and their Phase 1 domain invariants."""

from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domain.enums import AvailabilityStatus, ConfidenceLevel, SourceType
from app.domain.validation import build_variant_key, normalize_variant_attributes
from app.retailer_adapters.base.models import (
    NormalizedProduct,
    PriceObservation,
    ProductSearchQuery,
    SellerInformation,
)
from tests.unit.retailer_adapters.helpers import (
    FIXED_NOW,
    make_price_observation,
    make_retailer_product,
)


class TestPriceObservation:
    def test_requires_every_provenance_field(self) -> None:
        observation = make_price_observation()
        assert observation.retailer_id == "scripted-store"
        assert observation.seller is not None
        assert observation.source_url is not None
        assert observation.observed_at == FIXED_NOW
        assert observation.displayed_price == Decimal("999.00")
        assert observation.mrp == Decimal("1299.00")
        assert observation.availability is AvailabilityStatus.IN_STOCK
        assert observation.source_type is SourceType.OTHER_PERMITTED
        assert observation.confidence is ConfidenceLevel.HIGH

    def test_effective_price_may_be_absent(self) -> None:
        assert make_price_observation().effective_price is None

    def test_rejects_negative_displayed_price(self) -> None:
        with pytest.raises(ValidationError):
            make_price_observation(displayed_price="-1.00")

    def test_rejects_naive_timestamp(self) -> None:
        with pytest.raises(ValidationError):
            make_price_observation(observed_at=datetime(2026, 1, 15, 12, 0))

    def test_rejects_invalid_currency(self) -> None:
        with pytest.raises(ValidationError):
            PriceObservation(
                retailer_id="scripted-store",
                retailer_sku="SKU-1",
                observed_at=FIXED_NOW,
                currency="rupees",
                displayed_price=Decimal("1.00"),
                availability=AvailabilityStatus.IN_STOCK,
                source_type=SourceType.OTHER_PERMITTED,
                confidence=ConfidenceLevel.HIGH,
            )


class TestRetailerProduct:
    def test_rejects_embedded_observation_from_another_retailer(self) -> None:
        foreign_price = make_price_observation(retailer_id="other-store")
        with pytest.raises(ValidationError):
            make_retailer_product(price=foreign_price)

    def test_rejects_embedded_observation_for_a_different_sku(self) -> None:
        mismatched = make_price_observation(retailer_sku="OTHER")
        with pytest.raises(ValidationError):
            make_retailer_product(price=mismatched)


class TestNormalizedProduct:
    def test_variant_key_matches_phase1_domain_helper(self) -> None:
        product = NormalizedProduct(
            retailer_id="scripted-store",
            retailer_sku="SKU-1",
            normalized_title="fictional scripted phone",
            brand_name="Fictional Scripted Brand",
            brand_slug="fictional-scripted-brand",
            category_slug="mobiles",
            variant_attributes={" Colour ": " Black ", "Storage": "128 GB"},
            source_type=SourceType.OTHER_PERMITTED,
            normalized_at=FIXED_NOW,
        )
        expected_attributes = normalize_variant_attributes(
            {" Colour ": " Black ", "Storage": "128 GB"}
        )
        assert dict(product.variant_attributes) == expected_attributes
        assert product.variant_key == build_variant_key(expected_attributes)

    def test_rejects_empty_variant_attributes(self) -> None:
        with pytest.raises(ValidationError):
            NormalizedProduct(
                retailer_id="scripted-store",
                retailer_sku="SKU-1",
                normalized_title="untitled",
                variant_attributes={},
                source_type=SourceType.OTHER_PERMITTED,
                normalized_at=FIXED_NOW,
            )


class TestProductSearchQuery:
    def test_requires_text_or_category(self) -> None:
        with pytest.raises(ValidationError):
            ProductSearchQuery()

    def test_accepts_text_only(self) -> None:
        assert ProductSearchQuery(text="aurora").text == "aurora"

    def test_accepts_category_only(self) -> None:
        assert ProductSearchQuery(category="mobiles").category == "mobiles"


class TestSellerInformation:
    def test_first_party_and_marketplace_sellers_are_distinct(self) -> None:
        first_party = SellerInformation(name="Fictional Store", is_first_party=True)
        marketplace = SellerInformation(
            name="Fictional Third Party", retailer_seller_id="s-9", is_first_party=False
        )
        assert first_party.is_first_party is True
        assert marketplace.is_first_party is False
        assert first_party != marketplace
