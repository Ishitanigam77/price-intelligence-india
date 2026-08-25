"""RetailerProduct: a specific ProductVariant as listed by a specific Retailer.

This is the "Retailer Listing" of `PROJECT_ARCHITECTURE.md` §5's hierarchy
(Product -> ProductVariant -> RetailerProduct -> PriceSnapshot). It is the anchor that later
phases attach adapter-sourced data to: `retailer_sku` is the retailer's own native id for this
listing (e.g. an ASIN or FSN), captured once discovered by a collector — never fabricated.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.price_snapshot import PriceSnapshot
    from app.db.models.product_variant import ProductVariant
    from app.db.models.retailer import Retailer


class RetailerProduct(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A product variant as offered by a specific retailer (one row per retailer listing)."""

    __tablename__ = "retailer_products"
    __table_args__ = (
        UniqueConstraint(
            "retailer_id", "retailer_sku", name="uq_retailer_products_retailer_id_retailer_sku"
        ),
        Index("ix_retailer_products_product_variant_id", "product_variant_id"),
    )

    product_variant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=False
    )
    retailer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("retailers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    retailer_sku: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    product_variant: Mapped["ProductVariant"] = relationship(
        "ProductVariant", back_populates="retailer_products"
    )
    retailer: Mapped["Retailer"] = relationship("Retailer", back_populates="retailer_products")
    price_snapshots: Mapped[list["PriceSnapshot"]] = relationship(
        "PriceSnapshot", back_populates="retailer_product", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"RetailerProduct(id={self.id!r}, retailer_id={self.retailer_id!r}, "
            f"retailer_sku={self.retailer_sku!r})"
        )
