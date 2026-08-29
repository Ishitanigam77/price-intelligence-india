"""Unit tests for watchlist ownership enforcement at the service layer."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.errors import ConflictError, NotFoundError
from app.services.watchlist_service import WatchlistService


class _FakeWatchlists:
    def __init__(self) -> None:
        self.items: list[SimpleNamespace] = []
        self.session = SimpleNamespace(
            begin_nested=lambda: _NullCtx(),
            flush=lambda: None,
        )

    def get_by_user_and_product(self, user_id, product_id):
        return next(
            (
                item
                for item in self.items
                if item.user_id == user_id and item.product_id == product_id
            ),
            None,
        )

    def get_for_user(self, user_id, item_id):
        return next(
            (item for item in self.items if item.user_id == user_id and item.id == item_id),
            None,
        )

    def list_for_user(self, user_id, *, limit, offset):
        owned = [item for item in self.items if item.user_id == user_id]
        return owned[offset : offset + limit]

    def count_for_user(self, user_id):
        return sum(1 for item in self.items if item.user_id == user_id)

    def add(self, item):
        if getattr(item, "id", None) is None:
            item.id = uuid4()
        self.items.append(item)
        return item

    def delete(self, item):
        self.items.remove(item)


class _FakeProducts:
    def __init__(self, product_ids: set) -> None:
        self.product_ids = product_ids

    def get_by_id(self, product_id):
        return SimpleNamespace(id=product_id) if product_id in self.product_ids else None


class _NullCtx:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_list_returns_only_the_authenticated_users_items() -> None:
    owner = SimpleNamespace(id=uuid4())
    other = SimpleNamespace(id=uuid4())
    product_a, product_b = uuid4(), uuid4()
    repo = _FakeWatchlists()
    repo.add(SimpleNamespace(id=uuid4(), user_id=owner.id, product_id=product_a))
    repo.add(SimpleNamespace(id=uuid4(), user_id=other.id, product_id=product_b))
    service = WatchlistService(repo, _FakeProducts({product_a, product_b}))

    items, total = service.list_for_user(owner, limit=50, offset=0)
    assert total == 1
    assert items[0].product_id == product_a


def test_get_for_another_user_is_not_found() -> None:
    owner = SimpleNamespace(id=uuid4())
    other = SimpleNamespace(id=uuid4())
    product_id = uuid4()
    item_id = uuid4()
    repo = _FakeWatchlists()
    repo.add(SimpleNamespace(id=item_id, user_id=owner.id, product_id=product_id))
    service = WatchlistService(repo, _FakeProducts({product_id}))

    with pytest.raises(NotFoundError):
        service.get_for_user(other, item_id)


def test_duplicate_watchlist_is_conflict() -> None:
    owner = SimpleNamespace(id=uuid4())
    product_id = uuid4()
    repo = _FakeWatchlists()
    service = WatchlistService(repo, _FakeProducts({product_id}))
    service.create_for_user(owner, product_id)
    with pytest.raises(ConflictError):
        service.create_for_user(owner, product_id)


def test_invalid_product_is_not_found() -> None:
    owner = SimpleNamespace(id=uuid4())
    service = WatchlistService(_FakeWatchlists(), _FakeProducts(set()))
    with pytest.raises(NotFoundError):
        service.create_for_user(owner, uuid4())
