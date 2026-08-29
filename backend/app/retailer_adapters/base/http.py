"""Retailer-agnostic HTTP helpers for official API / affiliate-feed adapters.

This module knows nothing about any specific retailer. It translates transport failures into
the framework error taxonomy so adapter packages do not each re-implement timeout, 429, and
connection handling. Callers still pass their own timeout and must never log credentials or
raw payloads.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from app.retailer_adapters.base.errors import (
    AdapterMisconfiguredError,
    AdapterTimeoutError,
    AdapterUnavailableError,
    InvalidRetailerResponseError,
    ProductNotFoundError,
    RateLimitExceededError,
    TemporaryRetailerFailureError,
)


def parse_retry_after_seconds(response: httpx.Response) -> float | None:
    """Parse a `Retry-After` header as a delay in seconds, if present and valid."""
    raw = response.headers.get("Retry-After")
    if raw is None:
        return None
    stripped = raw.strip()
    if not stripped:
        return None
    try:
        return max(float(stripped), 0.0)
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(stripped)
        except (TypeError, ValueError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=UTC)
        return max((retry_at - datetime.now(UTC)).total_seconds(), 0.0)


def _raise_for_status(
    response: httpx.Response,
    *,
    retailer_id: str,
    operation: str,
    not_found_is_missing: bool,
) -> None:
    status = response.status_code
    if status < 400:
        return
    retry_after = parse_retry_after_seconds(response)
    if status == 429:
        raise RateLimitExceededError(
            "The source signalled that its published rate limit was reached.",
            retailer_id=retailer_id,
            operation=operation,
            retry_after_seconds=retry_after,
        )
    if status in {401, 403}:
        raise AdapterMisconfiguredError(
            "The source rejected the request as unauthorized.",
            retailer_id=retailer_id,
            operation=operation,
        )
    if status == 404 and not_found_is_missing:
        raise ProductNotFoundError(
            "The source reported that the requested listing does not exist.",
            retailer_id=retailer_id,
            operation=operation,
        )
    if status == 408:
        raise AdapterTimeoutError(
            "The source closed the request as a timeout.",
            retailer_id=retailer_id,
            operation=operation,
        )
    if status >= 500:
        raise TemporaryRetailerFailureError(
            "The source returned a transient server error.",
            retailer_id=retailer_id,
            operation=operation,
            retry_after_seconds=retry_after,
        )
    raise InvalidRetailerResponseError(
        f"The source returned an unexpected HTTP {status} status.",
        retailer_id=retailer_id,
        operation=operation,
    )


async def request_json(
    client: httpx.AsyncClient,
    *,
    method: str,
    url: str,
    retailer_id: str,
    operation: str,
    timeout_seconds: float,
    headers: Mapping[str, str] | None = None,
    json_body: Mapping[str, Any] | None = None,
    params: Mapping[str, str | int] | None = None,
    not_found_is_missing: bool = False,
) -> Any:
    """Perform one JSON HTTP call and return the decoded payload.

    Timeouts are always set. Failures become `RetailerAdapterError` subclasses. Response bodies
    are never copied into exception messages.
    """
    try:
        response = await client.request(
            method,
            url,
            headers=dict(headers or {}),
            json=dict(json_body) if json_body is not None else None,
            params=dict(params) if params is not None else None,
            timeout=timeout_seconds,
        )
    except httpx.TimeoutException as exc:
        raise AdapterTimeoutError(
            "The HTTP call exceeded its configured timeout.",
            retailer_id=retailer_id,
            operation=operation,
        ) from exc
    except httpx.RequestError as exc:
        raise AdapterUnavailableError(
            "The source could not be reached.",
            retailer_id=retailer_id,
            operation=operation,
        ) from exc

    _raise_for_status(
        response,
        retailer_id=retailer_id,
        operation=operation,
        not_found_is_missing=not_found_is_missing,
    )
    if not response.content:
        raise InvalidRetailerResponseError(
            "The source returned an empty body where JSON was required.",
            retailer_id=retailer_id,
            operation=operation,
        )
    try:
        return response.json()
    except json.JSONDecodeError as exc:
        raise InvalidRetailerResponseError(
            "The source returned a non-JSON body.",
            retailer_id=retailer_id,
            operation=operation,
        ) from exc


def require_mapping(payload: Any, *, retailer_id: str, operation: str) -> dict[str, Any]:
    """Reject a JSON payload that is not an object."""
    if not isinstance(payload, dict):
        raise InvalidRetailerResponseError(
            "The source returned JSON that was not an object.",
            retailer_id=retailer_id,
            operation=operation,
        )
    return payload
