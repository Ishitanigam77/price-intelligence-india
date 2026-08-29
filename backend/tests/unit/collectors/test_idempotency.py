"""Stable idempotency keys for collection jobs."""

from app.collectors.idempotency import build_idempotency_key
from app.domain.enums import CollectionJobType


def test_same_logical_parameters_produce_the_same_key() -> None:
    key_one = build_idempotency_key(
        CollectionJobType.PRODUCT_SEARCH,
        "mock-retailer-a",
        scope={"query": "fictional", "limit": 20},
    )
    key_two = build_idempotency_key(
        CollectionJobType.PRODUCT_SEARCH,
        "mock-retailer-a",
        scope={"limit": 20, "query": "fictional"},
    )
    assert key_one == key_two
    assert key_one.startswith("product_search|mock-retailer-a|")


def test_different_retailers_or_job_types_do_not_share_keys() -> None:
    search_a = build_idempotency_key(CollectionJobType.PRODUCT_SEARCH, "store-a")
    search_b = build_idempotency_key(CollectionJobType.PRODUCT_SEARCH, "store-b")
    price_a = build_idempotency_key(CollectionJobType.PRICE_REFRESH, "store-a")
    assert len({search_a, search_b, price_a}) == 3


def test_run_key_distinguishes_otherwise_identical_jobs() -> None:
    base = build_idempotency_key(CollectionJobType.PRICE_REFRESH, "store-a", scope={"skus": ["S1"]})
    other = build_idempotency_key(
        CollectionJobType.PRICE_REFRESH,
        "store-a",
        scope={"skus": ["S1"]},
        run_key="cycle-2",
    )
    assert base != other
