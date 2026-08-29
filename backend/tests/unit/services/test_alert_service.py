"""Unit tests for alert ownership isolation."""

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.errors import NotFoundError
from app.services.alert_service import AlertService


class _NullCtx:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _FakeAlerts:
    def __init__(self) -> None:
        self.items: list[SimpleNamespace] = []
        self.session = SimpleNamespace(begin_nested=lambda: _NullCtx(), flush=lambda: None)

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
        item.id = uuid4()
        self.items.append(item)
        return item

    def delete(self, item):
        self.items.remove(item)


class _FakeProducts:
    def __init__(self, ids: set) -> None:
        self.ids = ids

    def get_by_id(self, product_id):
        return SimpleNamespace(id=product_id) if product_id in self.ids else None


def test_alerts_are_isolated_by_owner() -> None:
    owner = SimpleNamespace(id=uuid4())
    other = SimpleNamespace(id=uuid4())
    product_id = uuid4()
    repo = _FakeAlerts()
    service = AlertService(repo, _FakeProducts({product_id}))
    created = service.create_for_user(
        owner,
        product_id,
        threshold_amount=Decimal("500.00"),
        currency="INR",
        is_enabled=True,
    )
    items, total = service.list_for_user(other, limit=50, offset=0)
    assert total == 0
    assert items == []
    with pytest.raises(NotFoundError):
        service.get_for_user(other, created.id)
