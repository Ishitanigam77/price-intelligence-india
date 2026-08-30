"""Structured (JSON) logging, per `DEVELOPMENT_RULES.md` §5.5.

Every log record is emitted as a single JSON object so deployed environments can index log
fields directly. Callers attach context as ordinary `logging` extras:

    logger.info("adapter.search_products", extra={"retailer_id": "example", "duration_ms": 12.3})

Any extra whose key looks like a credential (api key, token, password, ...) is redacted before
serialization, so an accidental `extra={"api_key": ...}` cannot leak a secret into the logs.
Redaction is a safety net, not a licence to pass secrets around: adapters must not put
credentials in log context in the first place.
"""

import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any, TextIO

REDACTED = "[REDACTED]"

_SENSITIVE_KEY_PATTERN = re.compile(
    r"(secret|token|password|passwd|api[-_ ]?key|apikey|authorization|auth[-_ ]?header"
    r"|credential|private[-_ ]?key|access[-_ ]?key|cookie|session[-_ ]?id"
    r"|connection[-_ ]?string|database[-_ ]?url|redis[-_ ]?url|broker[-_ ]?url"
    r"|result[-_ ]?backend|instrumentation[-_ ]?key|clerk[-_ ]?secret)",
    re.IGNORECASE,
)

_BEARER_IN_MESSAGE = re.compile(r"(?i)(bearer\s+)[^\s]+")
_ASSIGNMENT_IN_MESSAGE = re.compile(
    r"(?i)\b(api[-_]?key|token|password|secret|authorization|access[-_]?key"
    r"|connection[-_]?string)\s*[:=]\s*\S+"
)

#: Attributes present on every `LogRecord`; anything else was supplied by the caller via
#: `extra=` and therefore belongs in the structured payload. Derived from a real record so it
#: stays correct across Python versions (e.g. `taskName`, added in 3.12).
_RESERVED_RECORD_ATTRS = frozenset(
    vars(
        logging.LogRecord(
            name="", level=logging.INFO, pathname="", lineno=0, msg="", args=(), exc_info=None
        )
    )
) | {"message", "asctime", "taskName"}


def looks_sensitive(key: str) -> bool:
    """Whether a field name looks like it holds a credential.

    Shared by log redaction and by configuration validation, so both agree on what counts as a
    secret-looking key.
    """
    return _SENSITIVE_KEY_PATTERN.search(key) is not None


def redact(key: str, value: Any) -> Any:
    """Return `value` with credential-looking content replaced by `REDACTED`.

    Recurses into mappings and sequences so a nested `{"headers": {"authorization": ...}}` is
    redacted too.
    """
    if looks_sensitive(key):
        return REDACTED
    if isinstance(value, dict):
        return {str(inner_key): redact(str(inner_key), inner) for inner_key, inner in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [redact(key, item) for item in value]
    return value


def sanitize_log_message(message: str) -> str:
    """Redact credential-looking tokens that leaked into the log message text."""
    text = _BEARER_IN_MESSAGE.sub(rf"\1{REDACTED}", message)
    return _ASSIGNMENT_IN_MESSAGE.sub(lambda match: f"{match.group(1)}={REDACTED}", text)


class JsonLogFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects, including caller-supplied extras.

    Every record includes timestamp, level, service, environment, and (when bound)
    correlation_id. Credential-looking extras and message fragments are redacted.
    """

    def format(self, record: logging.LogRecord) -> str:
        from app.observability.context import get_environment, get_service
        from app.observability.correlation import get_correlation_id

        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": sanitize_log_message(record.getMessage()),
            "service": getattr(record, "service", None) or get_service(),
            "environment": getattr(record, "environment", None) or get_environment(),
        }
        correlation = getattr(record, "correlation_id", None) or get_correlation_id()
        if correlation:
            payload["correlation_id"] = correlation
        for key, value in vars(record).items():
            if key in _RESERVED_RECORD_ATTRS or key.startswith("_"):
                continue
            if key in payload:
                continue
            payload[key] = redact(key, value)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)
        return json.dumps(payload, default=str, sort_keys=True)


def configure_logging(level: str = "INFO", *, stream: TextIO | None = None) -> None:
    """Install the JSON formatter on the root logger.

    Called once during process startup (see `app.main`). Existing handlers are replaced so a
    process cannot end up emitting a mix of plain-text and JSON records.
    """
    handler = logging.StreamHandler(stream if stream is not None else sys.stdout)
    handler.setFormatter(JsonLogFormatter())

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level.upper())


def get_logger(name: str) -> logging.Logger:
    """Return a module-level logger so callers need not import `logging` directly."""
    return logging.getLogger(name)
