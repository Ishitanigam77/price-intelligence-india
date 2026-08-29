"""Watchlist service: create/list/get/delete for the authenticated user only."""

import uuid

from sqlalchemy.exc import IntegrityError

from app.api.errors import ConflictError, NotFoundError
from app.db.models.user import User
from app.db.models.watchlist_item import WatchlistItem
from app.repositories.product_repository import ProductRepository
from app.repositories.watchlist_repository import WatchlistRepository


class WatchlistService:
    def __init__(
        self,
        watchlists: WatchlistRepository,
        products: ProductRepository,
    ) -> None:
        self._watchlists = watchlists
        self._products = products

    def create_for_user(self, user: User, product_id: uuid.UUID) -> WatchlistItem:
        self._require_product(product_id)
        existing = self._watchlists.get_by_user_and_product(user.id, product_id)
        if existing is not None:
            raise ConflictError("This product is already on the watchlist.")
        item = WatchlistItem(user_id=user.id, product_id=product_id)
        try:
            with self._watchlists.session.begin_nested():
                self._watchlists.add(item)
            return item
        except IntegrityError as exc:
            raise ConflictError("This product is already on the watchlist.") from exc

    def list_for_user(
        self, user: User, *, limit: int, offset: int
    ) -> tuple[list[WatchlistItem], int]:
        return (
            self._watchlists.list_for_user(user.id, limit=limit, offset=offset),
            self._watchlists.count_for_user(user.id),
        )

    def get_for_user(self, user: User, item_id: uuid.UUID) -> WatchlistItem:
        item = self._watchlists.get_for_user(user.id, item_id)
        if item is None:
            raise NotFoundError(f"Watchlist item {item_id} was not found.")
        return item

    def delete_for_user(self, user: User, item_id: uuid.UUID) -> None:
        item = self.get_for_user(user, item_id)
        self._watchlists.delete(item)

    def _require_product(self, product_id: uuid.UUID) -> None:
        if self._products.get_by_id(product_id) is None:
            raise NotFoundError(f"Product {product_id} was not found.")
