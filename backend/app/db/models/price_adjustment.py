"""PriceAdjustment: an itemized, provenance-bearing adjustment on a PriceSnapshot.

Coupons, payment discounts, and cashback are stored here so the comparison engine can decide
— per offer — whether they are verified-eligible. Delivery and platform fees remain on
`PriceSnapshot` itself (observed columns); the engine synthesizes fee adjustments from those
columns at comparison time and never assumes a missing fee is zero.

Adjustments are immutable after insert, matching PriceSnapshot: a correction is a new row,
never an in-place edit.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base
from app.db.models.mixins import UUIDPrimaryKeyMixin
from app.domain.enums import AdjustmentEligibility, AdjustmentKind, ConfidenceLevel
from app.domain.validation import validate_non_negative_amount

if TYPE_CHECKING:
    from app.db.models.price_snapshot import PriceSnapshot

_MONEY = Numeric(12, 2)


class PriceAdjustment(UUIDPrimaryKeyMixin, Base):
    """One observed promotional (or other) adjustment attached to a price observation."""

    __tablename__ = "price_adjustments"
    __table_args__ = (
        CheckConstraint("amount IS NULL OR amount >= 0", name="amount_non_negative"),
        Index("ix_price_adjustments_price_snapshot_id", "price_snapshot_id"),
    )

    price_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("price_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[AdjustmentKind] = mapped_column(
        SAEnum(
            AdjustmentKind,
            name="adjustment_kind",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    amount: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    source: Mapped[str] = mapped_column(String(500), nullable=False)
    eligibility: Mapped[AdjustmentEligibility] = mapped_column(
        SAEnum(
            AdjustmentEligibility,
            name="adjustment_eligibility",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confidence: Mapped[ConfidenceLevel] = mapped_column(
        SAEnum(
            ConfidenceLevel,
            name="confidence_level",
            native_enum=True,
            create_type=False,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_func.now(), nullable=False
    )

    price_snapshot: Mapped["PriceSnapshot"] = relationship(
        "PriceSnapshot", back_populates="adjustments"
    )

    @validates("amount")
    def _validate_amount(self, key: str, value: Decimal | None) -> Decimal | None:
        return validate_non_negative_amount(value, field_name="amount")

    @validates("source")
    def _validate_source(self, key: str, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Adjustment source must not be blank.")
        return stripped

    def __repr__(self) -> str:
        return (
            f"PriceAdjustment(id={self.id!r}, kind={self.kind!r}, "
            f"eligibility={self.eligibility!r}, amount={self.amount!r})"
        )
