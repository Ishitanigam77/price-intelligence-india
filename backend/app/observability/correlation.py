"""Correlation IDs for tracing one logical operation across log records.

A correlation ID is set once at the edge of a logical operation (an HTTP request, a scheduled
collection run) and is then picked up automatically by anything that logs inside that scope,
including retailer adapters. Implemented with a `ContextVar` so it works for both synchronous
code and concurrent asyncio tasks without being passed through every function signature.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def new_correlation_id() -> str:
    """Generate a fresh correlation ID."""
    return uuid.uuid4().hex


def get_correlation_id() -> str | None:
    """Return the correlation ID for the current context, if one has been set."""
    return _correlation_id.get()


@contextmanager
def correlation_scope(correlation_id: str | None = None) -> Iterator[str]:
    """Bind a correlation ID for the duration of the `with` block.

    Generates one when not supplied. The previous value is always restored on exit, so nested
    scopes and concurrent tasks cannot corrupt each other's context.
    """
    resolved = correlation_id or new_correlation_id()
    token = _correlation_id.set(resolved)
    try:
        yield resolved
    finally:
        _correlation_id.reset(token)
