"""Process-level logging context: service name and environment.

Kept as ContextVars so tests and concurrent workers can override without mutating globals.
Correlation IDs live in `correlation.py` and are independent of this module.
"""

from __future__ import annotations

from contextvars import ContextVar

_service: ContextVar[str] = ContextVar("observability_service", default="backend")
_environment: ContextVar[str] = ContextVar("observability_environment", default="development")


def set_log_context(*, service: str, environment: str) -> None:
    """Bind service/environment for subsequent structured log records in this context."""
    _service.set(service.strip() or "backend")
    _environment.set(environment.strip() or "development")


def get_service() -> str:
    return _service.get()


def get_environment() -> str:
    return _environment.get()
