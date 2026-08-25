"""Integration tests for `Retailer` and `Seller`.

Covers: retailer slug/name uniqueness, country code validation, at most one first-party seller
per retailer, and uniqueness of (retailer_id, external_seller_id) when present.
"""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.exceptions import InvalidCountryCodeError
from tests.factories import make_retailer, make_seller


def test_retailer_slug_must_be_unique(db_session: Session) -> None:
    db_session.add(make_retailer(slug="fictional-mart"))
    db_session.flush()

    db_session.add(make_retailer(slug="fictional-mart"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_retailer_country_code_is_validated(db_session: Session) -> None:
    with pytest.raises(InvalidCountryCodeError):
        make_retailer(country_code="India")


def test_retailer_defaults_to_india(db_session: Session) -> None:
    retailer = make_retailer()
    db_session.add(retailer)
    db_session.flush()
    assert retailer.country_code == "IN"


def test_only_one_first_party_seller_allowed_per_retailer(db_session: Session) -> None:
    retailer = make_retailer()
    db_session.add(retailer)
    db_session.flush()

    db_session.add(make_seller(retailer, name="Retailer Direct", is_first_party=True))
    db_session.flush()

    db_session.add(make_seller(retailer, name="Retailer Direct (dup)", is_first_party=True))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_multiple_third_party_sellers_are_allowed(db_session: Session) -> None:
    retailer = make_retailer()
    db_session.add(retailer)
    db_session.flush()

    db_session.add(make_seller(retailer, name="Third Party A", is_first_party=False))
    db_session.add(make_seller(retailer, name="Third Party B", is_first_party=False))
    db_session.flush()


def test_external_seller_id_is_unique_per_retailer_when_present(db_session: Session) -> None:
    retailer = make_retailer()
    db_session.add(retailer)
    db_session.flush()

    db_session.add(make_seller(retailer, name="Seller A", external_seller_id="EXT-1"))
    db_session.flush()

    db_session.add(make_seller(retailer, name="Seller A Duplicate", external_seller_id="EXT-1"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_multiple_sellers_may_have_null_external_seller_id(db_session: Session) -> None:
    retailer = make_retailer()
    db_session.add(retailer)
    db_session.flush()

    db_session.add(make_seller(retailer, name="Seller Without External Id 1"))
    db_session.add(make_seller(retailer, name="Seller Without External Id 2"))
    db_session.flush()
