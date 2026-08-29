"""TargetPrice: the authenticated user's desired price for a product."""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.validation import validate_currency_code, validate_required_non_negative_amount

if TYPE_CHECKING:
    from app.db.models.product import Product
    from app.db.models.user import User

_MONEY = Numeric(12, 2)


class TargetPrice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A user-specific target price for a canonical product.

    One target price per (user, product). Amounts are user-stated goals, not observed retailer
    prices and not predictions.
    """

    __tablename__ = "target_prices"
    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_target_prices_user_id_product_id"),
        CheckConstraint("amount >= 0", name="amount_non_negative"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")

    user: Mapped["User"] = relationship("User", back_populates="target_prices")
    product: Mapped["Product"] = relationship("Product")

    @validates("amount")
    def _validate_amount(self, key: str, value: Decimal) -> Decimal:
        return validate_required_non_negative_amount(value, field_name="amount")

    @validates("currency")
    def _validate_currency(self, key: str, value: str) -> str:
        return validate_currency_code(value)

    def __repr__(self) -> str:
        return (
            f"TargetPrice(id={self.id!r}, user_id={self.user_id!r}, product_id={self.product_id!r})"
        )
