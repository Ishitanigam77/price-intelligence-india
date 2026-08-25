"""Integration tests for `PriceSnapshot`: the immutable price/availability observation.

Covers: non-negative amount check constraints, currency validation, availability/source_type/
confidence enums, historical ordering, and the deduplication uniqueness constraint on
(retailer_product_id, observed_at, seller).
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.enums import AvailabilityStatus, ConfidenceLevel, SourceType
from app.domain.exceptions import InvalidCurrencyCodeError, NegativeAmountError
from tests.factories import (
    make_price_snapshot,
    make_product,
    make_retailer,
    make_retailer_product,
    make_seller,
    make_variant,
)


@pytest.fixture()
def retailer_product(db_session: Session):
    product = make_product()
    variant = make_variant(product)
    retailer = make_retailer()
    db_session.add_all([variant, retailer])
    db_session.flush()
    rp = make_retailer_product(variant, retailer)
    db_session.add(rp)
    db_session.flush()
    return rp


def test_can_record_a_price_snapshot(db_session: Session, retailer_product) -> None:
    snapshot = make_price_snapshot(
        retailer_product,
        displayed_price=Decimal("1999.00"),
        mrp=Decimal("2499.00"),
        availability=AvailabilityStatus.IN_STOCK,
        source_type=SourceType.PRODUCT_FEED,
        confidence=ConfidenceLevel.HIGH,
    )
    db_session.add(snapshot)
    db_session.flush()

    assert snapshot.currency == "INR"
    assert snapshot.mrp == Decimal("2499.00")


def test_displayed_price_cannot_be_negative_at_domain_level(
    db_session: Session, retailer_product
) -> None:
    with pytest.raises(NegativeAmountError):
        make_price_snapshot(retailer_product, displayed_price=Decimal("-1"))


def test_negative_displayed_price_is_rejected_by_db_check_constraint(
    db_session: Session, retailer_product
) -> None:
    """The CHECK constraint is a real backstop, independent of the ORM-level validator.

    Inserted via raw SQL (bypassing `PriceSnapshot`'s `@validates` hooks entirely) to prove the
    database itself — not just the application — refuses a negative price.
    """
    from sqlalchemy import text

    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                """
                INSERT INTO price_snapshots
                    (id, retailer_product_id, observed_at, currency, displayed_price,
                     availability, source_type, confidence)
                VALUES
                    (gen_random_uuid(), :retailer_product_id, now(), 'INR', -5,
                     'in_stock', 'other_permitted', 'high')
                """
            ),
            {"retailer_product_id": retailer_product.id},
        )
        db_session.flush()


def test_currency_must_be_a_valid_iso_code(db_session: Session, retailer_product) -> None:
    with pytest.raises(InvalidCurrencyCodeError):
        make_price_snapshot(retailer_product, currency="rupees")


def test_history_is_returned_oldest_first(db_session: Session, retailer_product) -> None:
    from app.repositories.price_snapshot_repository import PriceSnapshotRepository

    now = datetime.now(UTC)
    older = make_price_snapshot(retailer_product, observed_at=now - timedelta(days=2))
    newer = make_price_snapshot(retailer_product, observed_at=now)
    db_session.add_all([newer, older])
    db_session.flush()

    repo = PriceSnapshotRepository(db_session)
    history = repo.history_for_retailer_product(retailer_product.id)

    assert [snap.id for snap in history] == [older.id, newer.id]


def test_latest_snapshot_is_the_most_recently_observed(
    db_session: Session, retailer_product
) -> None:
    from app.repositories.price_snapshot_repository import PriceSnapshotRepository

    now = datetime.now(UTC)
    older = make_price_snapshot(retailer_product, observed_at=now - timedelta(days=1))
    newer = make_price_snapshot(retailer_product, observed_at=now)
    db_session.add_all([older, newer])
    db_session.flush()

    repo = PriceSnapshotRepository(db_session)
    latest = repo.latest_for_retailer_product(retailer_product.id)

    assert latest.id == newer.id


def test_duplicate_observation_for_same_retailer_product_seller_and_time_is_rejected(
    db_session: Session, retailer_product
) -> None:
    observed_at = datetime.now(UTC)
    db_session.add(make_price_snapshot(retailer_product, observed_at=observed_at))
    db_session.flush()

    db_session.add(make_price_snapshot(retailer_product, observed_at=observed_at))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_duplicate_check_is_seller_aware(db_session: Session, retailer_product) -> None:
    observed_at = datetime.now(UTC)
    seller = make_seller(retailer_product.retailer, name="Third Party Seller")
    db_session.add(seller)
    db_session.flush()

    # Same retailer product + same instant, but different sellers: legitimately two offers.
    db_session.add(make_price_snapshot(retailer_product, observed_at=observed_at, seller_id=None))
    db_session.add(
        make_price_snapshot(retailer_product, observed_at=observed_at, seller_id=seller.id)
    )
    db_session.flush()
