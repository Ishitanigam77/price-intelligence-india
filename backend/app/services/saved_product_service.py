"""Saved-product service: create/list/get/delete for the authenticated user only."""

import uuid

from sqlalchemy.exc import IntegrityError

from app.api.errors import ConflictError, NotFoundError
from app.db.models.saved_product import SavedProduct
from app.db.models.user import User
from app.repositories.product_repository import ProductRepository
from app.repositories.saved_product_repository import SavedProductRepository


class SavedProductService:
    def __init__(
        self,
        saved_products: SavedProductRepository,
        products: ProductRepository,
    ) -> None:
        self._saved_products = saved_products
        self._products = products

    def create_for_user(self, user: User, product_id: uuid.UUID) -> SavedProduct:
        self._require_product(product_id)
        existing = self._saved_products.get_by_user_and_product(user.id, product_id)
        if existing is not None:
            raise ConflictError("This product is already saved.")
        item = SavedProduct(user_id=user.id, product_id=product_id)
        try:
            with self._saved_products.session.begin_nested():
                self._saved_products.add(item)
            return item
        except IntegrityError as exc:
            raise ConflictError("This product is already saved.") from exc

    def list_for_user(
        self, user: User, *, limit: int, offset: int
    ) -> tuple[list[SavedProduct], int]:
        return (
            self._saved_products.list_for_user(user.id, limit=limit, offset=offset),
            self._saved_products.count_for_user(user.id),
        )

    def get_for_user(self, user: User, item_id: uuid.UUID) -> SavedProduct:
        item = self._saved_products.get_for_user(user.id, item_id)
        if item is None:
            raise NotFoundError(f"Saved product {item_id} was not found.")
        return item

    def delete_for_user(self, user: User, item_id: uuid.UUID) -> None:
        item = self.get_for_user(user, item_id)
        self._saved_products.delete(item)

    def _require_product(self, product_id: uuid.UUID) -> None:
        if self._products.get_by_id(product_id) is None:
            raise NotFoundError(f"Product {product_id} was not found.")
