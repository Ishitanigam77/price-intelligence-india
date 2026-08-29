"""Builders and clearly-labeled fictional catalogues for Phase 10 ML tests.

None of these prices, retailers, brands, or sale windows represent real-world data.
They exist only so unit tests can exercise leakage-safe features, chronological splits,
training, and inference without fabricating production training history.
"""

from __future__ import annotations

import math
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
from app.pricing.config import PricingConfig
from app.pricing.history_models import HistoricalObservationPoint
from app.sales.config import SalesConfig
from app.sales.models import SaleEventRecord, SalePricePoint
from ml.config import MLConfig
from ml.features.engineering import FeatureEngineer

ANCHOR = datetime(2024, 1, 15, 12, 0, tzinfo=UTC)
PRODUCT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaa10")
BRAND_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbb10")
CATEGORY_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccc10")
RETAILER_A = UUID("11111111-1111-1111-1111-111111111110")
RETAILER_B = UUID("22222222-2222-2222-2222-222222222210")


def ml_config(**overrides: object) -> MLConfig:
    return MLConfig(_env_file=None, **overrides)


def engineer() -> FeatureEngineer:
    return FeatureEngineer(
        pricing_config=PricingConfig(_env_file=None),
        sales_config=SalesConfig(_env_file=None),
    )


def observation(
    *,
    snapshot_id: UUID | None = None,
    product_id: UUID = PRODUCT_ID,
    variant_id: UUID | None = None,
    retailer_id: UUID = RETAILER_A,
    listing_id: UUID | None = None,
    seller_id: UUID | None = None,
    displayed_price: Decimal | str = "999.00",
    effective_price: Decimal | str | None = None,
    mrp: Decimal | str | None = "1299.00",
    observed_at: datetime = ANCHOR,
    created_at: datetime | None = None,
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
    brand_id: UUID | None = BRAND_ID,
    category_id: UUID | None = CATEGORY_ID,
) -> SalePricePoint:
    def _dec(value: Decimal | str | None) -> Decimal | None:
        if value is None:
            return None
        return value if isinstance(value, Decimal) else Decimal(value)

    displayed = (
        displayed_price if isinstance(displayed_price, Decimal) else Decimal(displayed_price)
    )
    created = created_at if created_at is not None else observed_at
    rid = retailer_id
    point = HistoricalObservationPoint(
        snapshot_id=snapshot_id or uuid4(),
        product_id=product_id,
        product_variant_id=variant_id or UUID("dddddddd-dddd-dddd-dddd-dddddddddd10"),
        variant_key="color=black|storage=128gb",
        retailer_id=rid,
        retailer_slug="fictional-mart-a" if rid == RETAILER_A else "fictional-mart-b",
        retailer_name="FIXTURE Fictional Mart A"
        if rid == RETAILER_A
        else "FIXTURE Fictional Mart B",
        retailer_product_id=listing_id or uuid4(),
        seller_id=seller_id,
        source_url="https://fictional-mart.example.test/p/fixture",
        source_type=SourceType.PRODUCT_FEED,
        observed_at=observed_at,
        created_at=created,
        currency="INR",
        displayed_price=displayed,
        effective_price=_dec(effective_price),
        mrp=_dec(mrp),
        availability=AvailabilityStatus.IN_STOCK,
        confidence=confidence,
    )
    return SalePricePoint(observation=point, brand_id=brand_id, category_id=category_id)


def event_record(
    *,
    event_id: UUID | None = None,
    name: str = "FIXTURE: Fictional Seasonal Sale",
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    event_type: SaleEventType = SaleEventType.SEASONAL,
    source: SaleEventSource = SaleEventSource.MANUAL_CURATION,
    source_ref: str | None = "test.fixture",
    retailer_id: UUID | None = None,
    brand_id: UUID | None = None,
    category_id: UUID | None = None,
) -> SaleEventRecord:
    start = start_date if start_date is not None else ANCHOR + timedelta(days=90)
    end = end_date if end_date is not None else start + timedelta(days=7)
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
        confidence=ConfidenceLevel.HIGH,
    )


def fixture_catalog(
    *,
    listing_count: int = 8,
    sale_count: int = 12,
    prehistory_days: int = 90,
    sale_spacing_days: int = 30,
    sale_length_days: int = 7,
    step_days: int = 3,
) -> tuple[list[SalePricePoint], list[SaleEventRecord]]:
    """A multi-month fictional catalogue with regular prices and cheaper sale windows.

    Sale price for listing i is a deterministic fraction of its regular series so a model
    can learn a mapping in tests. This is not production training data.
    """
    retailers = (RETAILER_A, RETAILER_B)
    listings: list[tuple[UUID, UUID, UUID, int]] = []
    for index in range(listing_count):
        listings.append(
            (
                uuid4(),  # variant
                uuid4(),  # listing
                retailers[index % 2],
                10000 + index * 250,
            )
        )
    events = [
        event_record(
            name=f"FIXTURE: Fictional Sale {index + 1}",
            start_date=ANCHOR + timedelta(days=prehistory_days + index * sale_spacing_days),
            end_date=ANCHOR
            + timedelta(days=prehistory_days + index * sale_spacing_days + sale_length_days),
        )
        for index in range(sale_count)
    ]
    last_end = events[-1].end_date
    points: list[SalePricePoint] = []
    day = 0
    cursor = ANCHOR
    while cursor <= last_end:
        for variant_id, listing_id, retailer_id, base in listings:
            wave = 1.0 + 0.03 * math.sin(day / 11.0)
            regular = Decimal(str(round(base * wave, 2)))
            in_sale = any(event.start_date <= cursor <= event.end_date for event in events)
            price = (regular * Decimal("0.82")).quantize(Decimal("0.01")) if in_sale else regular
            points.append(
                observation(
                    product_id=PRODUCT_ID,
                    variant_id=variant_id,
                    listing_id=listing_id,
                    retailer_id=retailer_id,
                    displayed_price=price,
                    effective_price=price,
                    mrp=Decimal(str(base + 2000)),
                    observed_at=cursor,
                )
            )
        day += step_days
        cursor = ANCHOR + timedelta(days=day)
    return points, events


def seed_ids() -> tuple[UUID, UUID]:
    """Stable listing/variant ids for a single test series."""
    point = observation(observed_at=ANCHOR)
    return point.observation.retailer_product_id, point.observation.product_variant_id
