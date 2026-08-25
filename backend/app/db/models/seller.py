"""Seller: the entity actually fulfilling a listing on a retailer/marketplace.

Per `PROJECT_ARCHITECTURE.md` §5, a Seller is relevant on marketplaces with multiple sellers per
listing (e.g. Amazon.in, Flipkart); for a first-party retailer, the seller is the retailer
itself (`is_first_party=True`).
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.price_snapshot import PriceSnapshot
    from app.db.models.retailer import Retailer


class Seller(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A seller operating on a specific retailer/marketplace."""

    __tablename__ = "sellers"
    __table_args__ = (
        Index(
            "uq_sellers_retailer_id_external_seller_id",
            "retailer_id",
            "external_seller_id",
            unique=True,
            postgresql_where=text("external_seller_id IS NOT NULL"),
        ),
        Index(
            "uq_sellers_one_first_party_per_retailer",
            "retailer_id",
            unique=True,
            postgresql_where=text("is_first_party"),
        ),
    )

    retailer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("retailers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    external_seller_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_first_party: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    retailer: Mapped["Retailer"] = relationship("Retailer", back_populates="sellers")
    price_snapshots: Mapped[list["PriceSnapshot"]] = relationship(
        "PriceSnapshot", back_populates="seller"
    )

    def __repr__(self) -> str:
        return f"Seller(id={self.id!r}, retailer_id={self.retailer_id!r}, name={self.name!r})"
