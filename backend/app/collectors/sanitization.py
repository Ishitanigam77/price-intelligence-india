"""Strip credentials and secret-looking values before they reach logs or CollectionError rows."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from app.observability.logging import REDACTED, looks_sensitive, redact

_BEARER_PATTERN = re.compile(r"(?i)(bearer\s+)[^\s]+")
_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(api[-_]?key|token|password|secret|authorization|access[-_]?key)\s*[:=]\s*\S+"
)
_REDIS_USERINFO_PATTERN = re.compile(r"(?i)(rediss?://)([^/@]+)@")


def sanitize_text(value: str | None, *, max_length: int = 1000) -> str | None:
    """Return a log/DB-safe copy of `value`, or `None` if empty."""
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    text = _REDIS_USERINFO_PATTERN.sub(rf"\1{REDACTED}@", text)
    text = _BEARER_PATTERN.sub(rf"\1{REDACTED}", text)
    text = _ASSIGNMENT_PATTERN.sub(lambda match: f"{match.group(1)}={REDACTED}", text)
    text = _redact_url_userinfo(text)
    if len(text) > max_length:
        text = text[: max_length - 3] + "..."
    return text


def sanitize_mapping(payload: dict[str, Any]) -> dict[str, Any]:
    """Redact credential-looking keys in a structured log/metrics payload."""
    return {str(key): redact(str(key), value) for key, value in payload.items()}


def assert_no_secrets(payload: dict[str, Any]) -> None:
    """Raise if a credential-looking key survived sanitization with a real value."""
    for key, value in payload.items():
        if looks_sensitive(str(key)) and value != REDACTED:
            raise ValueError(f"Refusing to record secret-looking field {key!r}.")
        if isinstance(value, dict):
            assert_no_secrets(value)


def _redact_url_userinfo(text: str) -> str:
    try:
        parts = urlsplit(text)
    except ValueError:
        return text
    if not parts.scheme or not parts.netloc or "@" not in parts.netloc:
        return text
    host = parts.netloc.rsplit("@", 1)[-1]
    return urlunsplit((parts.scheme, f"{REDACTED}@{host}", parts.path, parts.query, parts.fragment))
