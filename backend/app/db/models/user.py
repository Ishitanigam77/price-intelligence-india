"""User: internal PostgreSQL representation of a Clerk-authenticated identity.

Clerk remains the identity provider. This table maps `clerk_user_id` (the external identity)
to an internal UUID used as the owner of watchlists, saved products, target prices, alerts,
and preferences. Application passwords are never stored.
"""

from typing import TYPE_CHECKING

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.price_alert import PriceAlert
    from app.db.models.saved_product import SavedProduct
    from app.db.models.target_price import TargetPrice
    from app.db.models.user_preference import UserPreference
    from app.db.models.watchlist_item import WatchlistItem


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An application user whose identity is owned by Clerk.

    `clerk_user_id` is the sole external identity identifier. Ownership of user-scoped
    resources is always derived from this mapping after backend token verification — never
    from a client-supplied user id.
    """

    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("clerk_user_id", name="uq_users_clerk_user_id"),)

    clerk_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    preference: Mapped["UserPreference | None"] = relationship(
        "UserPreference", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    watchlist_items: Mapped[list["WatchlistItem"]] = relationship(
        "WatchlistItem", back_populates="user", cascade="all, delete-orphan"
    )
    saved_products: Mapped[list["SavedProduct"]] = relationship(
        "SavedProduct", back_populates="user", cascade="all, delete-orphan"
    )
    target_prices: Mapped[list["TargetPrice"]] = relationship(
        "TargetPrice", back_populates="user", cascade="all, delete-orphan"
    )
    price_alerts: Mapped[list["PriceAlert"]] = relationship(
        "PriceAlert", back_populates="user", cascade="all, delete-orphan"
    )

    @validates("clerk_user_id")
    def _validate_clerk_user_id(self, key: str, value: str) -> str:
        stripped = (value or "").strip()
        if not stripped:
            raise ValueError("clerk_user_id must be a non-empty Clerk user identifier.")
        return stripped

    @validates("email")
    def _validate_email(self, key: str, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @validates("display_name")
    def _validate_display_name(self, key: str, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, clerk_user_id={self.clerk_user_id!r})"
