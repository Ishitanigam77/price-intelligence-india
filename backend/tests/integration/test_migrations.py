"""Validates that the Alembic migration chain applies and reverses cleanly.

This exercises the actual migration files (not `Base.metadata.create_all`), so a mistake in a
migration (e.g. forgetting to drop a native ENUM type on downgrade) is caught by the test suite
rather than discovered manually.
"""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, inspect

from alembic import command
from tests.db_settings import TEST_DATABASE_URL

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    return cfg


def test_there_is_exactly_one_migration_head() -> None:
    script = ScriptDirectory.from_config(_alembic_config())
    heads = script.get_heads()
    assert len(heads) == 1, f"expected a single migration head, got {heads}"


def test_upgrade_head_then_downgrade_base_round_trips_cleanly(db_engine: Engine) -> None:
    cfg = _alembic_config()

    # db_engine fixture already upgraded to head; prove downgrade removes everything Phase 1
    # added, then upgrade head restores it, leaving the schema in the same usable state.
    command.downgrade(cfg, "base")
    inspector = inspect(db_engine)
    remaining_tables = set(inspector.get_table_names()) - {"alembic_version"}
    assert remaining_tables == set()

    command.upgrade(cfg, "head")
    inspector = inspect(db_engine)
    tables = set(inspector.get_table_names())
    assert {
        "brands",
        "categories",
        "retailers",
        "products",
        "sellers",
        "product_variants",
        "product_identifiers",
        "retailer_products",
        "price_snapshots",
        "price_adjustments",
        "sale_events",
        "users",
        "user_preferences",
        "watchlists",
        "saved_products",
        "target_prices",
        "price_alerts",
        "collection_jobs",
        "collection_errors",
    }.issubset(tables)
