"""Integration tests for promotional `PriceAdjustment` persistence."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.enums import AdjustmentEligibility, AdjustmentKind, ConfidenceLevel
from app.domain.exceptions import NegativeAmountError
from tests.factories import (
    make_price_adjustment,
    make_price_snapshot,
    make_product,
    make_retailer,
    make_retailer_product,
    make_variant,
)


@pytest.fixture()
def snapshot(db_session: Session):
    product = make_product()
    variant = make_variant(product)
    retailer = make_retailer()
    db_session.add_all([variant, retailer])
    db_session.flush()
    listing = make_retailer_product(variant, retailer)
    db_session.add(listing)
    db_session.flush()
    snap = make_price_snapshot(listing, displayed_price=Decimal("999.00"))
    db_session.add(snap)
    db_session.flush()
    return snap


def test_can_record_a_verified_coupon_adjustment(db_session: Session, snapshot) -> None:
    row = make_price_adjustment(
        snapshot,
        kind=AdjustmentKind.COUPON,
        amount=Decimal("100.00"),
        source="test.observed_coupon",
        eligibility=AdjustmentEligibility.VERIFIED_ELIGIBLE,
        confidence=ConfidenceLevel.HIGH,
    )
    db_session.add(row)
    db_session.flush()
    assert row.kind is AdjustmentKind.COUPON
    assert row.eligibility is AdjustmentEligibility.VERIFIED_ELIGIBLE
    assert row.source == "test.observed_coupon"
    assert snapshot.adjustments == [row]


def test_negative_adjustment_amount_is_rejected(db_session: Session, snapshot) -> None:
    with pytest.raises(NegativeAmountError):
        make_price_adjustment(snapshot, amount=Decimal("-1.00"))


def test_negative_amount_is_rejected_by_db_check_constraint(db_session: Session, snapshot) -> None:
    from sqlalchemy import text

    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                """
                INSERT INTO price_adjustments
                    (id, price_snapshot_id, kind, amount, source, eligibility,
                     observed_at, confidence)
                VALUES
                    (gen_random_uuid(), :snapshot_id, 'coupon', -5.00,
                     'raw-sql', 'verified_eligible', :observed_at, 'high')
                """
            ),
            {"snapshot_id": snapshot.id, "observed_at": datetime.now(UTC)},
        )
        db_session.flush()


def test_adjustments_are_deleted_when_snapshot_is_deleted(db_session: Session, snapshot) -> None:
    db_session.add(make_price_adjustment(snapshot))
    db_session.flush()
    db_session.delete(snapshot)
    db_session.flush()
    remaining = db_session.execute(text("SELECT count(*) FROM price_adjustments")).scalar()
    assert remaining == 0
