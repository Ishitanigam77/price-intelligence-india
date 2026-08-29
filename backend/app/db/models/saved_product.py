"""SavedProduct: a product the authenticated user has saved for later."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.product import Product
    from app.db.models.user import User


class SavedProduct(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A user-owned saved-product record.

    Distinct from a watchlist item: saving and watching are separate user actions with separate
    uniqueness constraints. Ownership is always the authenticated internal user.
    """

    __tablename__ = "saved_products"
    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_saved_products_user_id_product_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )

    user: Mapped["User"] = relationship("User", back_populates="saved_products")
    product: Mapped["Product"] = relationship("Product")

    def __repr__(self) -> str:
        return (
            f"SavedProduct(id={self.id!r}, user_id={self.user_id!r}, "
            f"product_id={self.product_id!r})"
        )
