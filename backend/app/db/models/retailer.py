"""Retailer: an Indian online retailer/marketplace tracked by the platform.

This is a reference/metadata table only — it records *that* a retailer exists and some basic
descriptive facts about it. No adapter, scraping, or API-integration logic is implemented here;
that is Phase 2's `RetailerAdapter` interface (see `RETAILER_ARCHITECTURE.md`). Keeping this
table retailer-agnostic in shape (no retailer-specific columns) is what lets the platform scale
to 100+ retailers without schema changes per retailer.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.validation import validate_country_code, validate_slug

if TYPE_CHECKING:
    from app.db.models.retailer_product import RetailerProduct
    from app.db.models.seller import Seller


class Retailer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A retailer/marketplace, e.g. a large e-commerce site or a smaller niche Indian store."""

    __tablename__ = "retailers"

    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(220), nullable=False, unique=True)
    website_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False, default="IN")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    sellers: Mapped[list["Seller"]] = relationship(
        "Seller", back_populates="retailer", cascade="all, delete-orphan"
    )
    retailer_products: Mapped[list["RetailerProduct"]] = relationship(
        "RetailerProduct", back_populates="retailer", cascade="all, delete-orphan"
    )

    @validates("slug")
    def _validate_slug(self, key: str, value: str) -> str:
        return validate_slug(value)

    @validates("country_code")
    def _validate_country_code(self, key: str, value: str) -> str:
        return validate_country_code(value)

    def __repr__(self) -> str:
        return f"Retailer(id={self.id!r}, slug={self.slug!r})"
