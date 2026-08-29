"""WatchlistItem: authenticated-user ↔ product association."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.product import Product
    from app.db.models.user import User


class WatchlistItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A product on a user's watchlist.

    Duplicate (user, product) rows are rejected by a uniqueness constraint. The owner is always
    the authenticated internal user — this table has no client-writable owner column in the API.
    """

    __tablename__ = "watchlists"
    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_watchlists_user_id_product_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )

    user: Mapped["User"] = relationship("User", back_populates="watchlist_items")
    product: Mapped["Product"] = relationship("Product")

    def __repr__(self) -> str:
        return (
            f"WatchlistItem(id={self.id!r}, user_id={self.user_id!r}, "
            f"product_id={self.product_id!r})"
        )
