"""ProductIdentifier: a cross-retailer identifier (GTIN/EAN/UPC/ISBN/MPN) for a variant.

These identifiers are what lets a future matching engine (Phase 3) recognize that two different
retailers' listings refer to the same real-world product variant, per `DATA_FLOW.md` §2.3's
matching preference order (identifiers first, before text/embedding-based matching).
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.enums import ProductIdentifierType

if TYPE_CHECKING:
    from app.db.models.product_variant import ProductVariant


class ProductIdentifier(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single typed identifier value attached to a `ProductVariant`."""

    __tablename__ = "product_identifiers"
    __table_args__ = (
        UniqueConstraint(
            "identifier_type", "value", name="uq_product_identifiers_identifier_type_value"
        ),
    )

    product_variant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    identifier_type: Mapped[ProductIdentifierType] = mapped_column(
        SAEnum(
            ProductIdentifierType,
            name="product_identifier_type",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    value: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    product_variant: Mapped["ProductVariant"] = relationship(
        "ProductVariant", back_populates="identifiers"
    )

    def __repr__(self) -> str:
        return (
            f"ProductIdentifier(id={self.id!r}, type={self.identifier_type!r}, "
            f"value={self.value!r})"
        )
