"""Category: a (possibly nested) product classification, e.g. Electronics > Mobiles."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.validation import validate_slug

if TYPE_CHECKING:
    from app.db.models.product import Product


class Category(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A product category. Self-referential to support a category tree.

    Categories are deliberately simple in Phase 1 (name/slug/parent) — category-driven browsing,
    facets, and category-specific matching rules belong to later phases.
    """

    __tablename__ = "categories"
    __table_args__ = (Index("ix_categories_parent_id", "parent_id"),)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    parent: Mapped["Category | None"] = relationship(
        "Category", remote_side="Category.id", back_populates="children"
    )
    children: Mapped[list["Category"]] = relationship("Category", back_populates="parent")
    products: Mapped[list["Product"]] = relationship("Product", back_populates="category")

    @validates("slug")
    def _validate_slug(self, key: str, value: str) -> str:
        return validate_slug(value)

    def __repr__(self) -> str:
        return f"Category(id={self.id!r}, slug={self.slug!r})"
