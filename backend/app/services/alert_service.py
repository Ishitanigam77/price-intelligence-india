"""Price-alert service: create/list/get/update/delete for the authenticated user only.

Notification dispatch is not implemented in this phase. Rules are persisted and authorized
here; delivery belongs to a later notifications increment.
"""

import uuid
from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from app.api.errors import ConflictError, NotFoundError
from app.db.models.price_alert import PriceAlert
from app.db.models.user import User
from app.repositories.price_alert_repository import PriceAlertRepository
from app.repositories.product_repository import ProductRepository


class AlertService:
    def __init__(
        self,
        alerts: PriceAlertRepository,
        products: ProductRepository,
    ) -> None:
        self._alerts = alerts
        self._products = products

    def create_for_user(
        self,
        user: User,
        product_id: uuid.UUID,
        *,
        threshold_amount: Decimal,
        currency: str,
        is_enabled: bool,
    ) -> PriceAlert:
        self._require_product(product_id)
        existing = self._alerts.get_by_user_and_product(user.id, product_id)
        if existing is not None:
            raise ConflictError("An alert already exists for this product.")
        item = PriceAlert(
            user_id=user.id,
            product_id=product_id,
            threshold_amount=threshold_amount,
            currency=currency,
            is_enabled=is_enabled,
        )
        try:
            with self._alerts.session.begin_nested():
                self._alerts.add(item)
            return item
        except IntegrityError as exc:
            raise ConflictError("An alert already exists for this product.") from exc

    def list_for_user(self, user: User, *, limit: int, offset: int) -> tuple[list[PriceAlert], int]:
        return (
            self._alerts.list_for_user(user.id, limit=limit, offset=offset),
            self._alerts.count_for_user(user.id),
        )

    def get_for_user(self, user: User, item_id: uuid.UUID) -> PriceAlert:
        item = self._alerts.get_for_user(user.id, item_id)
        if item is None:
            raise NotFoundError(f"Alert {item_id} was not found.")
        return item

    def update_for_user(
        self,
        user: User,
        item_id: uuid.UUID,
        *,
        threshold_amount: Decimal | None = None,
        currency: str | None = None,
        is_enabled: bool | None = None,
    ) -> PriceAlert:
        item = self.get_for_user(user, item_id)
        if threshold_amount is not None:
            item.threshold_amount = threshold_amount
        if currency is not None:
            item.currency = currency
        if is_enabled is not None:
            item.is_enabled = is_enabled
        self._alerts.session.flush()
        return item

    def delete_for_user(self, user: User, item_id: uuid.UUID) -> None:
        item = self.get_for_user(user, item_id)
        self._alerts.delete(item)

    def _require_product(self, product_id: uuid.UUID) -> None:
        if self._products.get_by_id(product_id) is None:
            raise NotFoundError(f"Product {product_id} was not found.")
