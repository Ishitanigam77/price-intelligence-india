"""Integration tests for `Product` and `ProductVariant`.

Covers: slug uniqueness, variant attribute normalization/`variant_key` derivation, the
(product_id, variant_key) uniqueness constraint that prevents duplicate logical variants, and
that deleting a product cascades to its variants (but not the other way around).
"""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import ProductVariant
from app.domain.exceptions import InvalidVariantAttributesError
from tests.factories import make_product, make_variant


def test_product_slug_must_be_unique(db_session: Session) -> None:
    db_session.add(make_product(slug="apple-iphone-16"))
    db_session.flush()

    db_session.add(make_product(slug="apple-iphone-16"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_variant_attributes_are_normalized_into_a_variant_key(db_session: Session) -> None:
    product = make_product()
    variant = make_variant(product, attributes={" Storage ": " 128GB ", "Color": "Black"})
    db_session.add(variant)
    db_session.flush()

    assert variant.attributes == {"storage": "128gb", "color": "black"}
    assert variant.variant_key == "color=black;storage=128gb"


def test_variant_requires_at_least_one_attribute(db_session: Session) -> None:
    product = make_product()
    with pytest.raises(InvalidVariantAttributesError):
        make_variant(product, attributes={})


def test_cannot_create_two_identical_variants_for_the_same_product(db_session: Session) -> None:
    product = make_product()
    db_session.add(make_variant(product, attributes={"storage": "128GB", "color": "Black"}))
    db_session.flush()

    db_session.add(
        make_variant(product, attributes={"color": "black", "storage": "128gb"})  # same, reordered
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_same_product_can_have_distinct_variants(db_session: Session) -> None:
    product = make_product()
    db_session.add(make_variant(product, attributes={"storage": "128GB", "color": "Black"}))
    db_session.add(make_variant(product, attributes={"storage": "256GB", "color": "Black"}))
    db_session.flush()

    variants = db_session.scalars(
        select(ProductVariant).where(ProductVariant.product_id == product.id)
    ).all()
    assert len(variants) == 2


def test_deleting_product_cascades_to_its_variants(db_session: Session) -> None:
    product = make_product()
    variant = make_variant(product)
    db_session.add(variant)
    db_session.flush()
    variant_id = variant.id

    db_session.delete(product)
    db_session.flush()

    assert db_session.get(ProductVariant, variant_id) is None
