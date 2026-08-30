"""Structured (JSON) application logging configuration.

Per `DEVELOPMENT_RULES.md` §5.5, the application uses structured logging rather than ad-hoc
`print`/debug statements. The log level is configurable via `LOG_LEVEL` (see
`app.core.config.Settings`); the format defaults to JSON lines, which is friendly to log
aggregation in containerized/cloud deployments (Docker, Kubernetes, Azure Monitor).

This module delegates formatting and secret redaction to `app.observability.logging` so API,
worker, and adapter logs share one schema (timestamp, service, environment, correlation ID).
"""

import logging
import sys

from app.core.config import Settings
from app.observability.context import set_log_context
from app.observability.logging import JsonLogFormatter

_CONFIGURED = False


def configure_logging(settings: Settings) -> None:
    """Configure the root logger once per process.

    Idempotent: safe to call multiple times (e.g. once from the app factory, once from test
    setup) without installing duplicate handlers.
    """
    global _CONFIGURED
    set_log_context(service=settings.service_name, environment=settings.environment)
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level)

    if _CONFIGURED:
        return

    handler = logging.StreamHandler(stream=sys.stdout)
    if settings.log_format.lower() == "json":
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))

    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Quiet noisy third-party loggers unless explicitly debugging.
    logging.getLogger("uvicorn.access").setLevel(settings.log_level)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.WARNING if settings.log_level != "DEBUG" else logging.INFO
    )

    _CONFIGURED = True


# Re-export so existing imports of JsonFormatter keep working.
JsonFormatter = JsonLogFormatter
