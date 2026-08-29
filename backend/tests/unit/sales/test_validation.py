"""Unit tests for sale-event domain validation."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.enums import SaleEventSource, SaleEventType
from app.domain.exceptions import InvalidSaleEventError
from app.domain.validation import validate_sale_event, validate_sale_event_dates
from tests.unit.sales.helpers import NOW


def test_end_before_start_is_rejected() -> None:
    with pytest.raises(InvalidSaleEventError):
        validate_sale_event_dates(NOW, NOW - timedelta(seconds=1))


def test_naive_bounds_are_rejected() -> None:
    naive = datetime(2026, 8, 28, 12, 0)
    with pytest.raises(InvalidSaleEventError):
        validate_sale_event_dates(naive, naive + timedelta(days=1))


def test_retailer_specific_requires_retailer() -> None:
    with pytest.raises(InvalidSaleEventError, match="retailer_id"):
        validate_sale_event(
            event_type=SaleEventType.RETAILER_SPECIFIC,
            source=SaleEventSource.MANUAL_CURATION,
            source_ref="test.fixture",
            retailer_id=None,
            category_id=None,
            brand_id=None,
            start_date=NOW,
            end_date=NOW + timedelta(days=1),
        )


def test_brand_and_category_require_scope() -> None:
    with pytest.raises(InvalidSaleEventError, match="brand_id"):
        validate_sale_event(
            event_type=SaleEventType.BRAND,
            source=SaleEventSource.MANUAL_CURATION,
            source_ref="test.fixture",
            retailer_id=None,
            category_id=None,
            brand_id=None,
            start_date=NOW,
            end_date=NOW + timedelta(days=1),
        )
    with pytest.raises(InvalidSaleEventError, match="category_id"):
        validate_sale_event(
            event_type=SaleEventType.CATEGORY,
            source=SaleEventSource.MANUAL_CURATION,
            source_ref="test.fixture",
            retailer_id=None,
            category_id=None,
            brand_id=None,
            start_date=NOW,
            end_date=NOW + timedelta(days=1),
        )


def test_manually_curated_requires_manual_source() -> None:
    with pytest.raises(InvalidSaleEventError, match="manual_curation"):
        validate_sale_event(
            event_type=SaleEventType.MANUALLY_CURATED,
            source=SaleEventSource.PRODUCT_FEED,
            source_ref="test.fixture",
            retailer_id=None,
            category_id=None,
            brand_id=None,
            start_date=NOW,
            end_date=NOW + timedelta(days=1),
        )


def test_externally_sourced_requires_permitted_source_and_ref() -> None:
    with pytest.raises(InvalidSaleEventError, match="legitimate permitted source"):
        validate_sale_event(
            event_type=SaleEventType.EXTERNALLY_SOURCED,
            source=SaleEventSource.MANUAL_CURATION,
            source_ref="https://example.test/feed",
            retailer_id=None,
            category_id=None,
            brand_id=None,
            start_date=NOW,
            end_date=NOW + timedelta(days=1),
        )
    with pytest.raises(InvalidSaleEventError, match="source_ref"):
        validate_sale_event(
            event_type=SaleEventType.EXTERNALLY_SOURCED,
            source=SaleEventSource.PRODUCT_FEED,
            source_ref="   ",
            retailer_id=None,
            category_id=None,
            brand_id=None,
            start_date=NOW,
            end_date=NOW + timedelta(days=1),
        )


def test_valid_externally_sourced_event() -> None:
    ref = validate_sale_event(
        event_type=SaleEventType.EXTERNALLY_SOURCED,
        source=SaleEventSource.OFFICIAL_API,
        source_ref="  https://partner.example.test/sale-calendar  ",
        retailer_id=None,
        category_id=None,
        brand_id=None,
        start_date=NOW,
        end_date=NOW + timedelta(days=2),
    )
    assert ref == "https://partner.example.test/sale-calendar"


def test_observed_inference_cannot_be_labeled_external() -> None:
    with pytest.raises(InvalidSaleEventError, match="not an externally sourced"):
        validate_sale_event(
            event_type=SaleEventType.EXTERNALLY_SOURCED,
            source=SaleEventSource.OBSERVED_PRICE_INFERENCE,
            source_ref="calculated.observed_price_inference",
            retailer_id=uuid4(),
            category_id=None,
            brand_id=None,
            start_date=NOW,
            end_date=NOW + timedelta(days=1),
        )
