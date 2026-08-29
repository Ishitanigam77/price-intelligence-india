"""PriceAlert: authenticated-user alert rule for a product threshold."""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.validation import validate_currency_code, validate_required_non_negative_amount

if TYPE_CHECKING:
    from app.db.models.product import Product
    from app.db.models.user import User

_MONEY = Numeric(12, 2)


class PriceAlert(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A user-owned price-alert rule.

    Notification dispatch is out of scope for this phase. This record stores the rule
    (product, threshold, enabled state) so it can be listed and authorized. One alert per
    (user, product).
    """

    __tablename__ = "price_alerts"
    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_price_alerts_user_id_product_id"),
        CheckConstraint("threshold_amount >= 0", name="threshold_amount_non_negative"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    threshold_amount: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    user: Mapped["User"] = relationship("User", back_populates="price_alerts")
    product: Mapped["Product"] = relationship("Product")

    @validates("threshold_amount")
    def _validate_threshold(self, key: str, value: Decimal) -> Decimal:
        return validate_required_non_negative_amount(value, field_name="threshold_amount")

    @validates("currency")
    def _validate_currency(self, key: str, value: str) -> str:
        return validate_currency_code(value)

    def __repr__(self) -> str:
        return (
            f"PriceAlert(id={self.id!r}, user_id={self.user_id!r}, product_id={self.product_id!r})"
        )
