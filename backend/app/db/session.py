"""Database engine and session factory.

Repositories and API dependencies obtain sessions from here; nothing above this module should
construct a SQLAlchemy engine directly.
"""

from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def create_db_engine(database_url: str | None = None) -> Engine:
    """Create a new SQLAlchemy engine for the given (or configured) database URL.

    Pool sizing is read from `Settings` (`db_pool_size`, `db_max_overflow`, `db_pool_timeout`,
    `db_pool_recycle`) so it can be tuned per environment (e.g. smaller pools for local dev,
    larger ones behind a production load balancer) without code changes.
    """
    settings = get_settings()
    url = database_url or settings.database_url
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_recycle=settings.db_pool_recycle,
        future=True,
    )


engine: Engine = create_db_engine()
SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine, autocommit=False, autoflush=False, future=True
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI-style dependency yielding a session, committing on success, always closed.

    Write paths (product discovery persistence) require a commit at the end of a successful
    request. Failures roll back so a partial persist never becomes visible. Test suites that
    need transaction isolation override this dependency rather than relying on this commit.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
