"""Shared fixtures for integration tests.

Integration tests run against a real PostgreSQL database (per `TECH_STACK.md` — no SQLite
fallback is used, since we want to exercise the actual Postgres-specific features the schema
relies on: native ENUM types, JSONB, partial unique indexes, and expression indexes).

The target database is configured via the `TEST_DATABASE_URL` environment variable (falling
back to a local `priceradar_test` database matching `.env.example`'s conventions). Each test
gets its own session bound to a SAVEPOINT that is rolled back afterwards, so tests never leak
state into one another and never require manual cleanup.
"""

import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from tests.db_settings import TEST_DATABASE_URL

BACKEND_DIR = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def db_engine() -> Generator[Engine, None, None]:
    """Ensure the test database is migrated to `head`, then hand back an engine for it."""
    from alembic.config import Config

    from alembic import command

    alembic_cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(TEST_DATABASE_URL, future=True)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(db_engine: Engine) -> Generator[Session, None, None]:
    """A session whose changes are always rolled back at the end of the test."""
    connection = db_engine.connect()
    outer_transaction = connection.begin()
    session_factory = sessionmaker(bind=connection, future=True)
    session = session_factory()

    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess: Session, transaction) -> None:
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    try:
        yield session
    finally:
        session.close()
        outer_transaction.rollback()
        connection.close()


@pytest.fixture()
def unique_suffix() -> str:
    """A short unique string to keep test-created slugs/names collision-free."""
    return uuid.uuid4().hex[:8]
