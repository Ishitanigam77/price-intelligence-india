"""Database engine and session factory.

Repositories and API dependencies obtain sessions from here; nothing above this module should
construct a SQLAlchemy engine directly.
"""

from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def create_db_engine(database_url: str | None = None) -> Engine:
    """Create a new SQLAlchemy engine for the given (or configured) database URL."""
    url = database_url or get_settings().database_url
    return create_engine(url, pool_pre_ping=True, future=True)


engine: Engine = create_db_engine()
SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine, autocommit=False, autoflush=False, future=True
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI-style dependency yielding a session and guaranteeing it is closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
