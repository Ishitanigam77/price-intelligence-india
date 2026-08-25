"""Structured (JSON) application logging configuration.

Per `DEVELOPMENT_RULES.md` §5.5, the application uses structured logging rather than ad-hoc
`print`/debug statements. The log level is configurable via `LOG_LEVEL` (see
`app.core.config.Settings`); the format defaults to JSON lines, which is friendly to log
aggregation in containerized/cloud deployments (Docker, Kubernetes, Azure Monitor).

Nothing in this module ever logs secrets/credentials: application code is responsible for not
passing sensitive values into log messages, and `app.core.config.Settings` values (which may
include connection strings) must never be logged verbatim.
"""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from app.core.config import Settings

_CONFIGURED = False

_RESERVED_RECORD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)


class JsonFormatter(logging.Formatter):
    """Renders each log record as a single JSON line.

    Includes any extra fields passed via `logger.info(..., extra={...})` so request-scoped
    context (e.g. request path, status code) can be attached without string formatting.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED_RECORD_ATTRS and key not in payload:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(settings: Settings) -> None:
    """Configure the root logger once per process.

    Idempotent: safe to call multiple times (e.g. once from the app factory, once from test
    setup) without installing duplicate handlers.
    """
    global _CONFIGURED
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level)

    if _CONFIGURED:
        return

    handler = logging.StreamHandler(stream=sys.stdout)
    if settings.log_format.lower() == "json":
        handler.setFormatter(JsonFormatter())
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
