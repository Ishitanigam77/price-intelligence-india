"""Integration tests for `ProductIdentifier`: type/value uniqueness across variants."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.enums import ProductIdentifierType
from tests.factories import make_identifier, make_product, make_variant


def test_identifier_type_and_value_pair_must_be_globally_unique(db_session: Session) -> None:
    product = make_product()
    variant_a = make_variant(product, attributes={"storage": "128GB"})
    variant_b = make_variant(product, attributes={"storage": "256GB"})
    db_session.add_all([variant_a, variant_b])
    db_session.flush()

    db_session.add(
        make_identifier(
            variant_a, identifier_type=ProductIdentifierType.GTIN, value="1234567890123"
        )
    )
    db_session.flush()

    # The same GTIN value cannot legitimately belong to a second, different variant.
    db_session.add(
        make_identifier(
            variant_b, identifier_type=ProductIdentifierType.GTIN, value="1234567890123"
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_same_variant_can_have_multiple_identifier_types(db_session: Session) -> None:
    product = make_product()
    variant = make_variant(product)
    db_session.add(variant)
    db_session.flush()

    db_session.add(make_identifier(variant, identifier_type=ProductIdentifierType.GTIN))
    db_session.add(make_identifier(variant, identifier_type=ProductIdentifierType.MPN))
    db_session.flush()

    assert len(variant.identifiers) == 2
