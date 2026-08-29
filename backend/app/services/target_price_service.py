"""Target-price service: create/list/get/update/delete for the authenticated user only."""

import uuid
from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from app.api.errors import ConflictError, NotFoundError
from app.db.models.target_price import TargetPrice
from app.db.models.user import User
from app.repositories.product_repository import ProductRepository
from app.repositories.target_price_repository import TargetPriceRepository


class TargetPriceService:
    def __init__(
        self,
        target_prices: TargetPriceRepository,
        products: ProductRepository,
    ) -> None:
        self._target_prices = target_prices
        self._products = products

    def create_for_user(
        self,
        user: User,
        product_id: uuid.UUID,
        *,
        amount: Decimal,
        currency: str,
    ) -> TargetPrice:
        self._require_product(product_id)
        existing = self._target_prices.get_by_user_and_product(user.id, product_id)
        if existing is not None:
            raise ConflictError("A target price already exists for this product.")
        item = TargetPrice(user_id=user.id, product_id=product_id, amount=amount, currency=currency)
        try:
            with self._target_prices.session.begin_nested():
                self._target_prices.add(item)
            return item
        except IntegrityError as exc:
            raise ConflictError("A target price already exists for this product.") from exc

    def list_for_user(
        self, user: User, *, limit: int, offset: int
    ) -> tuple[list[TargetPrice], int]:
        return (
            self._target_prices.list_for_user(user.id, limit=limit, offset=offset),
            self._target_prices.count_for_user(user.id),
        )

    def get_for_user(self, user: User, item_id: uuid.UUID) -> TargetPrice:
        item = self._target_prices.get_for_user(user.id, item_id)
        if item is None:
            raise NotFoundError(f"Target price {item_id} was not found.")
        return item

    def update_for_user(
        self,
        user: User,
        item_id: uuid.UUID,
        *,
        amount: Decimal | None = None,
        currency: str | None = None,
    ) -> TargetPrice:
        item = self.get_for_user(user, item_id)
        if amount is not None:
            item.amount = amount
        if currency is not None:
            item.currency = currency
        self._target_prices.session.flush()
        return item

    def delete_for_user(self, user: User, item_id: uuid.UUID) -> None:
        item = self.get_for_user(user, item_id)
        self._target_prices.delete(item)

    def _require_product(self, product_id: uuid.UUID) -> None:
        if self._products.get_by_id(product_id) is None:
            raise NotFoundError(f"Product {product_id} was not found.")
