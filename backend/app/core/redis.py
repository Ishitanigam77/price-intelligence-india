"""Redis connection/client management.

Phase 2 scope only: infrastructure to configure a Redis connection pool, hand out a client via
FastAPI dependency injection, and check connectivity for the readiness endpoint. No caching
business logic, distributed locks, queues, or notification logic is implemented here — those
are introduced by whichever later phase actually needs them (see `ROADMAP.md`).
"""

from collections.abc import Generator
from functools import lru_cache

import redis
from redis import Redis

from app.core.config import get_settings


@lru_cache
def get_redis_pool() -> redis.ConnectionPool:
    """Build (and cache) the process-wide Redis connection pool from the configured URL."""
    settings = get_settings()
    return redis.ConnectionPool.from_url(
        settings.redis_url,
        max_connections=settings.redis_max_connections,
        socket_timeout=settings.redis_socket_timeout,
        socket_connect_timeout=settings.redis_socket_connect_timeout,
    )


def create_redis_client() -> Redis:
    """Create a new Redis client bound to the shared, process-wide connection pool."""
    return redis.Redis(connection_pool=get_redis_pool())


def get_redis() -> Generator[Redis, None, None]:
    """FastAPI-style dependency yielding a Redis client from the shared connection pool.

    The client itself is a thin, connection-pooled handle — nothing to close per-request beyond
    letting it go out of scope, since the underlying pool is process-scoped and released on
    application shutdown (see `app.main`'s lifespan handler).
    """
    yield create_redis_client()


def check_redis_connection(client: Redis | None = None) -> bool:
    """Return whether Redis responds to `PING`. Used by the readiness endpoint.

    Never raises: connection errors are treated as "not ready" rather than propagated, so the
    caller can build a clear structured response instead of a raw stack trace.
    """
    try:
        target = client or create_redis_client()
        return bool(target.ping())
    except redis.RedisError:
        return False


def close_redis_pool() -> None:
    """Dispose of the cached connection pool. Called on application shutdown."""
    if get_redis_pool.cache_info().currsize:
        pool = get_redis_pool()
        pool.disconnect()
    get_redis_pool.cache_clear()
