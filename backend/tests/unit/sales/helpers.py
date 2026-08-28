"""Builders for sale-event unit tests. All data is fictional fixture data."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from app.domain.enums import (
    AvailabilityStatus,
    ConfidenceLevel,
    SaleEventSource,
    SaleEventType,
    SourceType,
)
from app.pricing.history_models import HistoricalObservationPoint
from app.sales.config import SalesConfig
from app.sales.detection import SaleEventDetector
from app.sales.engine import SaleEventEngine
from app.sales.history import SaleHistoryEngine
from app.sales.models import SaleEventRecord, SalePricePoint

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)

PRODUCT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
VARIANT_A = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
VARIANT_B = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
RETAILER_A = UUID("11111111-1111-1111-1111-111111111111")
RETAILER_B = UUID("22222222-2222-2222-2222-222222222222")
BRAND_A = UUID("33333333-3333-3333-3333-333333333333")
CATEGORY_A = UUID("44444444-4444-4444-4444-444444444444")


def sales_config(**overrides: object) -> SalesConfig:
    return SalesConfig(_env_file=None, **overrides)


def event_record(
    *,
    event_id: UUID | None = None,
    name: str = "FIXTURE: Fictional Seasonal Sale",
    event_type: SaleEventType = SaleEventType.SEASONAL,
    source: SaleEventSource = SaleEventSource.MANUAL_CURATION,
    source_ref: str | None = "test.fixture",
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    retailer_id: UUID | None = None,
    category_id: UUID | None = None,
    brand_id: UUID | None = None,
) -> SaleEventRecord:
    start = start_date if start_date is not None else NOW
    end = end_date if end_date is not None else NOW + timedelta(days=7)
    if event_type is SaleEventType.RETAILER_SPECIFIC and retailer_id is None:
        retailer_id = RETAILER_A
    if event_type is SaleEventType.BRAND and brand_id is None:
        brand_id = BRAND_A
    if event_type is SaleEventType.CATEGORY and category_id is None:
        category_id = CATEGORY_A
    if event_type is SaleEventType.EXTERNALLY_SOURCED:
        if source not in {
            SaleEventSource.OFFICIAL_API,
            SaleEventSource.AFFILIATE_FEED,
            SaleEventSource.PRODUCT_FEED,
            SaleEventSource.OTHER_PERMITTED,
        }:
            source = SaleEventSource.PRODUCT_FEED
        source_ref = source_ref or "test.fixture.permitted-feed"
    return SaleEventRecord(
        id=event_id or uuid4(),
        name=name,
        retailer_id=retailer_id,
        category_id=category_id,
        brand_id=brand_id,
        start_date=start,
        end_date=end,
        event_type=event_type,
        source=source,
        source_ref=source_ref,
        confidence=confidence,
    )


def observation(
    *,
    snapshot_id: UUID | None = None,
    product_id: UUID = PRODUCT_ID,
    variant_id: UUID = VARIANT_A,
    retailer_id: UUID = RETAILER_A,
    listing_id: UUID | None = None,
    seller_id: UUID | None = None,
    displayed_price: Decimal | str = "999.00",
    effective_price: Decimal | str | None = None,
    observed_at: datetime = NOW,
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
    brand_id: UUID | None = BRAND_A,
    category_id: UUID | None = CATEGORY_A,
) -> SalePricePoint:
    def _dec(value: Decimal | str | None) -> Decimal | None:
        if value is None:
            return None
        return value if isinstance(value, Decimal) else Decimal(value)

    displayed = (
        displayed_price if isinstance(displayed_price, Decimal) else Decimal(displayed_price)
    )
    point = HistoricalObservationPoint(
        snapshot_id=snapshot_id or uuid4(),
        product_id=product_id,
        product_variant_id=variant_id,
        variant_key="color=black|storage=128gb",
        retailer_id=retailer_id,
        retailer_slug="fictional-mart-a" if retailer_id == RETAILER_A else "fictional-mart-b",
        retailer_name="Fictional Mart A" if retailer_id == RETAILER_A else "Fictional Mart B",
        retailer_product_id=listing_id or uuid4(),
        seller_id=seller_id,
        source_url="https://fictional-mart.example.test/p/1",
        source_type=SourceType.PRODUCT_FEED,
        observed_at=observed_at,
        created_at=observed_at,
        currency="INR",
        displayed_price=displayed,
        effective_price=_dec(effective_price),
        mrp=None,
        availability=AvailabilityStatus.IN_STOCK,
        confidence=confidence,
    )
    return SalePricePoint(observation=point, brand_id=brand_id, category_id=category_id)


def history_engine(config: SalesConfig | None = None) -> SaleHistoryEngine:
    return SaleHistoryEngine(config=config or sales_config(), clock=lambda: NOW)


def detector(config: SalesConfig | None = None) -> SaleEventDetector:
    return SaleEventDetector(config=config or sales_config(), clock=lambda: NOW)


def engine(config: SalesConfig | None = None) -> SaleEventEngine:
    return SaleEventEngine(config=config or sales_config(), clock=lambda: NOW)
