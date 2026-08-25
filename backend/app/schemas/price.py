"""API schemas for `PriceSnapshot` (the "Price Observation" of `PROJECT_ARCHITECTURE.md` §5/§6).

These schemas expose exactly the fields the `PriceSnapshot` model already carries — they do not
compute, derive, or predict anything (no price comparison, effective-price calculation, or
drop-detection logic; that belongs to Phase 4). Observed, calculated, and predicted values are
kept visibly distinct per `DEVELOPMENT_RULES.md` §3.5: this schema only ever reflects data that
was already stored as an immutable observation.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.domain.enums import AvailabilityStatus, ConfidenceLevel, SourceType


class PriceSnapshotRead(BaseModel):
    """Public representation of a single immutable price/availability observation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    retailer_product_id: uuid.UUID
    seller_id: uuid.UUID | None = None
    observed_at: datetime
    currency: str
    mrp: Decimal | None = None
    displayed_price: Decimal
    effective_price: Decimal | None = None
    delivery_fee: Decimal | None = None
    platform_fee: Decimal | None = None
    availability: AvailabilityStatus
    source_type: SourceType
    source_url: str | None = None
    confidence: ConfidenceLevel
    created_at: datetime
