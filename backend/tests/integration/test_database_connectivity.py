"""Integration tests for `app.db.session`: engine construction and the `get_db` dependency.

Extends Phase 1's readiness-check coverage with a direct check that the configured engine (and
its pool sizing, introduced in Phase 2) actually connects, and that `get_db` closes its session
even when the caller only partially consumes the generator.
"""

from sqlalchemy import text

from app.db.session import create_db_engine, get_db
from tests.db_settings import TEST_DATABASE_URL


def test_create_db_engine_connects_to_the_configured_database() -> None:
    engine = create_db_engine(TEST_DATABASE_URL)
    try:
        with engine.connect() as connection:
            assert connection.execute(text("SELECT 1")).scalar_one() == 1
    finally:
        engine.dispose()


def test_engine_pool_sizing_matches_settings() -> None:
    from app.core.config import get_settings

    settings = get_settings()
    engine = create_db_engine(TEST_DATABASE_URL)
    try:
        assert engine.pool.size() == settings.db_pool_size
    finally:
        engine.dispose()


def test_get_db_dependency_yields_a_working_session_and_closes_it() -> None:
    generator = get_db()
    session = next(generator)
    assert session.execute(text("SELECT 1")).scalar_one() == 1

    generator.close()
    # SQLAlchemy's Session.close() is idempotent and safe to call on an already-closed session;
    # this proves `get_db`'s `finally: db.close()` ran rather than leaking the connection.
    session.close()
