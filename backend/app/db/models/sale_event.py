"""SaleEvent: a named sale window with optional retailer/category/brand scope.

This is the persisted form of sale-event intelligence (`PROJECT_ARCHITECTURE.md` §4, `app/sales`).
Lifecycle status (before/during/after) is derived from `start_date`/`end_date` and is never
stored. Event names and dates must come from curation, a legitimate permitted source, or
calculated inference over stored observations — never invented real-world campaigns.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, event
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.enums import ConfidenceLevel, SaleEventSource, SaleEventType
from app.domain.validation import normalize_sale_event_source_ref, validate_sale_event

if TYPE_CHECKING:
    from app.db.models.brand import Brand
    from app.db.models.category import Category
    from app.db.models.retailer import Retailer


class SaleEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A sale window that may apply to a retailer, brand, category, or the catalogue at large."""

    __tablename__ = "sale_events"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="end_date_not_before_start_date"),
        Index("ix_sale_events_start_date", "start_date"),
        Index("ix_sale_events_end_date", "end_date"),
        Index("ix_sale_events_event_type", "event_type"),
        Index("ix_sale_events_source", "source"),
        Index("ix_sale_events_retailer_id", "retailer_id"),
        Index("ix_sale_events_category_id", "category_id"),
        Index("ix_sale_events_brand_id", "brand_id"),
        Index("ix_sale_events_start_date_end_date", "start_date", "end_date"),
    )

    name: Mapped[str] = mapped_column(String(500), nullable=False)
    retailer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("retailers.id", ondelete="RESTRICT"), nullable=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), nullable=True
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("brands.id", ondelete="RESTRICT"), nullable=True
    )
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_type: Mapped[SaleEventType] = mapped_column(
        SAEnum(
            SaleEventType,
            name="sale_event_type",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    source: Mapped[SaleEventSource] = mapped_column(
        SAEnum(
            SaleEventSource,
            name="sale_event_source",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    source_ref: Mapped[str | None] = mapped_column(String(2048), nullable=True)
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

    retailer: Mapped["Retailer | None"] = relationship("Retailer", back_populates="sale_events")
    category: Mapped["Category | None"] = relationship("Category", back_populates="sale_events")
    brand: Mapped["Brand | None"] = relationship("Brand", back_populates="sale_events")

    @validates("name")
    def _validate_name(self, key: str, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Sale event name must not be blank.")
        return stripped

    @validates("source_ref")
    def _validate_source_ref(self, key: str, value: str | None) -> str | None:
        return normalize_sale_event_source_ref(value)

    def __repr__(self) -> str:
        return (
            f"SaleEvent(id={self.id!r}, name={self.name!r}, event_type={self.event_type!r}, "
            f"start_date={self.start_date!r}, end_date={self.end_date!r})"
        )


@event.listens_for(SaleEvent, "before_insert")
@event.listens_for(SaleEvent, "before_update")
def _validate_sale_event_invariants(mapper, connection, target: SaleEvent) -> None:
    """Cross-field window/scope/source checks; runs before the row is written."""
    target.source_ref = validate_sale_event(
        event_type=target.event_type,
        source=target.source,
        source_ref=target.source_ref,
        retailer_id=target.retailer_id,
        category_id=target.category_id,
        brand_id=target.brand_id,
        start_date=target.start_date,
        end_date=target.end_date,
    )
