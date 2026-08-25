"""Integration tests for `app.core.redis`: connection pool, client, and health check.

Runs against a real local Redis instance (see `REDIS_URL` in `.env.example`) — no fakeredis or
other in-memory substitute, matching the same "test against the real infrastructure dependency"
approach the Phase 1 database tests use.
"""

import redis

from app.core.redis import check_redis_connection, create_redis_client, get_redis


def test_create_redis_client_can_ping_a_reachable_redis() -> None:
    client = create_redis_client()
    assert client.ping() is True


def test_check_redis_connection_returns_true_when_reachable() -> None:
    assert check_redis_connection() is True


def test_check_redis_connection_returns_false_when_unreachable() -> None:
    unreachable_client = redis.Redis(
        host="127.0.0.1",
        port=1,  # nothing listens here
        socket_connect_timeout=0.2,
        socket_timeout=0.2,
    )
    assert check_redis_connection(unreachable_client) is False


def test_check_redis_connection_never_raises_on_a_bad_host() -> None:
    """Readiness must degrade gracefully, never 500 with a raw connection-error traceback."""
    bad_client = redis.Redis(
        host="redis-host-that-does-not-exist.invalid",
        port=6379,
        socket_connect_timeout=0.2,
    )
    assert check_redis_connection(bad_client) is False


def test_get_redis_dependency_yields_a_working_client() -> None:
    generator = get_redis()
    client = next(generator)
    try:
        assert client.ping() is True
    finally:
        generator.close()
