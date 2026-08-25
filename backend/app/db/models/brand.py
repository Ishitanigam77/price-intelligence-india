"""Brand: a product manufacturer/brand, e.g. "Apple", "Samsung", "boAt"."""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.validation import validate_slug

if TYPE_CHECKING:
    from app.db.models.product import Product


class Brand(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A product brand/manufacturer."""

    __tablename__ = "brands"

    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(220), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    products: Mapped[list["Product"]] = relationship("Product", back_populates="brand")

    @validates("slug")
    def _validate_slug(self, key: str, value: str) -> str:
        return validate_slug(value)

    def __repr__(self) -> str:
        return f"Brand(id={self.id!r}, slug={self.slug!r})"
