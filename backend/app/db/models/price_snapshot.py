"""PriceSnapshot: an immutable, timestamped price/availability observation.

This is the "Price Observation" of `PROJECT_ARCHITECTURE.md` §5/§6 and
`RETAILER_ARCHITECTURE.md` §6. Every field required by that contract (retailer — implied via
`retailer_product` — seller, source URL, observed_at, displayed price, MRP, effective price,
availability, source type, confidence) is present here.

Snapshots are never updated after creation: a correction is a new snapshot, never an edit to an
existing one. This module intentionally exposes no update path (see
`app.repositories.price_snapshot_repository`); it is enforced procedurally in Phase 1 and may
be hardened with a DB trigger in a later phase if needed.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base
from app.db.models.mixins import UUIDPrimaryKeyMixin
from app.domain.enums import AvailabilityStatus, ConfidenceLevel, SourceType
from app.domain.validation import (
    validate_currency_code,
    validate_non_negative_amount,
    validate_required_non_negative_amount,
)

if TYPE_CHECKING:
    from app.db.models.price_adjustment import PriceAdjustment
    from app.db.models.retailer_product import RetailerProduct
    from app.db.models.seller import Seller

#: Sentinel used (via COALESCE) in the deduplication unique index below so that "no specific
#: seller" (first-party/unspecified) snapshots are deduplicated the same way as seller-specific
#: ones. NULL is deliberately not relied on for uniqueness, since SQL treats every NULL as
#: distinct from every other NULL.
_NO_SELLER_SENTINEL = "00000000-0000-0000-0000-000000000000"

_MONEY = Numeric(12, 2)


class PriceSnapshot(UUIDPrimaryKeyMixin, Base):
    """An immutable point-in-time price/availability observation for a `RetailerProduct`."""

    __tablename__ = "price_snapshots"
    __table_args__ = (
        CheckConstraint("displayed_price >= 0", name="displayed_price_non_negative"),
        CheckConstraint("mrp IS NULL OR mrp >= 0", name="mrp_non_negative"),
        CheckConstraint(
            "effective_price IS NULL OR effective_price >= 0", name="effective_price_non_negative"
        ),
        CheckConstraint(
            "delivery_fee IS NULL OR delivery_fee >= 0", name="delivery_fee_non_negative"
        ),
        CheckConstraint(
            "platform_fee IS NULL OR platform_fee >= 0", name="platform_fee_non_negative"
        ),
        Index("ix_price_snapshots_observed_at", "observed_at"),
        Index(
            "ix_price_snapshots_retailer_product_id_observed_at",
            "retailer_product_id",
            "observed_at",
        ),
        Index(
            "uq_price_snapshots_dedupe",
            "retailer_product_id",
            "observed_at",
            text(f"COALESCE(seller_id, '{_NO_SELLER_SENTINEL}'::uuid)"),
            unique=True,
        ),
    )

    retailer_product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("retailer_products.id", ondelete="CASCADE"), nullable=False
    )
    seller_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sellers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    mrp: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    displayed_price: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    effective_price: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    delivery_fee: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    platform_fee: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    availability: Mapped[AvailabilityStatus] = mapped_column(
        SAEnum(
            AvailabilityStatus,
            name="availability_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    source_type: Mapped[SourceType] = mapped_column(
        SAEnum(
            SourceType,
            name="source_type",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[ConfidenceLevel] = mapped_column(
        SAEnum(
            ConfidenceLevel,
            name="confidence_level",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_func.now(), nullable=False
    )

    retailer_product: Mapped["RetailerProduct"] = relationship(
        "RetailerProduct", back_populates="price_snapshots"
    )
    seller: Mapped["Seller | None"] = relationship("Seller", back_populates="price_snapshots")
    adjustments: Mapped[list["PriceAdjustment"]] = relationship(
        "PriceAdjustment",
        back_populates="price_snapshot",
        cascade="all, delete-orphan",
    )

    @validates("currency")
    def _validate_currency(self, key: str, value: str) -> str:
        return validate_currency_code(value)

    @validates("mrp")
    def _validate_mrp(self, key: str, value: Decimal | None) -> Decimal | None:
        return validate_non_negative_amount(value, field_name="mrp")

    @validates("displayed_price")
    def _validate_displayed_price(self, key: str, value: Decimal) -> Decimal:
        return validate_required_non_negative_amount(value, field_name="displayed_price")

    @validates("effective_price")
    def _validate_effective_price(self, key: str, value: Decimal | None) -> Decimal | None:
        return validate_non_negative_amount(value, field_name="effective_price")

    @validates("delivery_fee")
    def _validate_delivery_fee(self, key: str, value: Decimal | None) -> Decimal | None:
        return validate_non_negative_amount(value, field_name="delivery_fee")

    @validates("platform_fee")
    def _validate_platform_fee(self, key: str, value: Decimal | None) -> Decimal | None:
        return validate_non_negative_amount(value, field_name="platform_fee")

    def __repr__(self) -> str:
        return (
            f"PriceSnapshot(id={self.id!r}, retailer_product_id={self.retailer_product_id!r}, "
            f"observed_at={self.observed_at!r}, displayed_price={self.displayed_price!r})"
        )
