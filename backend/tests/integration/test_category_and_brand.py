"""Integration tests for `Category` and `Brand`: hierarchy, slugs, and uniqueness."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.exceptions import InvalidSlugError
from tests.factories import make_brand, make_category


def test_category_can_have_a_parent(db_session: Session) -> None:
    parent = make_category(name="Electronics", slug="electronics")
    child = make_category(name="Mobiles", slug="electronics-mobiles", parent=parent)
    db_session.add_all([parent, child])
    db_session.flush()

    assert child.parent_id == parent.id
    assert child in parent.children


def test_category_slug_must_be_unique(db_session: Session) -> None:
    db_session.add(make_category(slug="duplicate-category"))
    db_session.flush()

    db_session.add(make_category(slug="duplicate-category"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_category_rejects_invalid_slug(db_session: Session) -> None:
    with pytest.raises(InvalidSlugError):
        make_category(slug="Not A Valid Slug")


def test_brand_name_and_slug_are_unique(db_session: Session) -> None:
    db_session.add(make_brand(name="Acme", slug="acme"))
    db_session.flush()

    db_session.add(make_brand(name="Acme", slug="acme-2"))
    with pytest.raises(IntegrityError):
        db_session.flush()
