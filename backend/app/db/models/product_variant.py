"""ProductVariant: a specific configuration of a Product (e.g. 128GB / Black)."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.validation import build_variant_key, normalize_variant_attributes

if TYPE_CHECKING:
    from app.db.models.product import Product
    from app.db.models.product_identifier import ProductIdentifier
    from app.db.models.retailer_product import RetailerProduct


class ProductVariant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A specific, sellable configuration of a `Product` (storage, color, size, ...).

    Per `PROJECT_ARCHITECTURE.md` §5, variants are never merged with each other even if
    superficially similar — a 128GB/Black iPhone and a 256GB/Black iPhone are always distinct
    rows. `variant_key` is a normalized, deterministic string derived from `attributes` and is
    what the (`product_id`, `variant_key`) uniqueness constraint is enforced against, so the
    same logical variant can never be inserted twice under a product.
    """

    __tablename__ = "product_variants"
    __table_args__ = (
        UniqueConstraint(
            "product_id", "variant_key", name="uq_product_variants_product_variant_key"
        ),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    attributes: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    variant_key: Mapped[str] = mapped_column(String(1000), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    product: Mapped["Product"] = relationship("Product", back_populates="variants")
    identifiers: Mapped[list["ProductIdentifier"]] = relationship(
        "ProductIdentifier", back_populates="product_variant", cascade="all, delete-orphan"
    )
    retailer_products: Mapped[list["RetailerProduct"]] = relationship(
        "RetailerProduct", back_populates="product_variant", cascade="all, delete-orphan"
    )

    @validates("attributes")
    def _validate_attributes(self, key: str, value: dict[str, str]) -> dict[str, str]:
        normalized = normalize_variant_attributes(value)
        self.variant_key = build_variant_key(normalized)
        return normalized

    def __repr__(self) -> str:
        return f"ProductVariant(id={self.id!r}, variant_key={self.variant_key!r})"
