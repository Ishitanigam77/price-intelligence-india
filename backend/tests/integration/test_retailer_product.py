"""Integration tests for `RetailerProduct`: the same variant listed by multiple retailers, and
uniqueness of (retailer_id, retailer_sku)."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.factories import make_product, make_retailer, make_retailer_product, make_variant


def test_same_variant_can_be_listed_by_multiple_retailers(db_session: Session) -> None:
    product = make_product()
    variant = make_variant(product)
    retailer_a = make_retailer()
    retailer_b = make_retailer()
    db_session.add_all([variant, retailer_a, retailer_b])
    db_session.flush()

    db_session.add(make_retailer_product(variant, retailer_a))
    db_session.add(make_retailer_product(variant, retailer_b))
    db_session.flush()

    assert len(variant.retailer_products) == 2


def test_retailer_sku_must_be_unique_within_a_retailer(db_session: Session) -> None:
    product = make_product()
    variant = make_variant(product)
    retailer = make_retailer()
    db_session.add_all([variant, retailer])
    db_session.flush()

    db_session.add(make_retailer_product(variant, retailer, retailer_sku="SKU-123"))
    db_session.flush()

    db_session.add(make_retailer_product(variant, retailer, retailer_sku="SKU-123"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_same_retailer_sku_is_allowed_across_different_retailers(db_session: Session) -> None:
    product = make_product()
    variant = make_variant(product)
    retailer_a = make_retailer()
    retailer_b = make_retailer()
    db_session.add_all([variant, retailer_a, retailer_b])
    db_session.flush()

    db_session.add(make_retailer_product(variant, retailer_a, retailer_sku="SKU-SAME"))
    db_session.add(make_retailer_product(variant, retailer_b, retailer_sku="SKU-SAME"))
    db_session.flush()
