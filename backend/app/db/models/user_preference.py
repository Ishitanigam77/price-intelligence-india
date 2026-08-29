"""UserPreference: per-user application settings that Clerk does not own."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.validation import validate_currency_code

if TYPE_CHECKING:
    from app.db.models.user import User


class UserPreference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Preferences belonging to exactly one internal user.

    Notification *dispatch* is out of scope for this phase; `email_alerts_enabled` is stored so
    a later notifications phase can honour it. Passwords are never stored here.
    """

    __tablename__ = "user_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    email_alerts_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    default_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")

    user: Mapped["User"] = relationship("User", back_populates="preference")

    @validates("default_currency")
    def _validate_currency(self, key: str, value: str) -> str:
        return validate_currency_code(value)

    def __repr__(self) -> str:
        return f"UserPreference(user_id={self.user_id!r})"
