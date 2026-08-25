"""Product: a distinct real-world product (e.g. "Apple iPhone 16"), independent of retailer."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.validation import validate_slug

if TYPE_CHECKING:
    from app.db.models.brand import Brand
    from app.db.models.category import Category
    from app.db.models.product_variant import ProductVariant


class Product(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A canonical, retailer-agnostic product.

    Per `PROJECT_ARCHITECTURE.md` §5, a Product is the top of the hierarchy:
    Product -> ProductVariant -> RetailerProduct -> PriceSnapshot. It never itself carries a
    price or availability — those belong to variants as offered by specific retailers.
    """

    __tablename__ = "products"
    __table_args__ = (
        Index("ix_products_brand_id", "brand_id"),
        Index("ix_products_category_id", "category_id"),
    )

    name: Mapped[str] = mapped_column(String(500), nullable=False)
    slug: Mapped[str] = mapped_column(String(550), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("brands.id", ondelete="RESTRICT"), nullable=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    brand: Mapped["Brand | None"] = relationship("Brand", back_populates="products")
    category: Mapped["Category | None"] = relationship("Category", back_populates="products")
    variants: Mapped[list["ProductVariant"]] = relationship(
        "ProductVariant", back_populates="product", cascade="all, delete-orphan"
    )

    @validates("slug")
    def _validate_slug(self, key: str, value: str) -> str:
        return validate_slug(value)

    def __repr__(self) -> str:
        return f"Product(id={self.id!r}, slug={self.slug!r})"
