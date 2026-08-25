"""Declarative base shared by every ORM model.

A consistent naming convention is applied to every constraint/index so that Alembic
autogenerate produces stable, predictable names (e.g. `ix_products_slug`,
`uq_categories_slug`, `ck_price_snapshots_displayed_price_non_negative`) instead of the
database's default anonymous names.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base class for all PriceRadar India ORM models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
