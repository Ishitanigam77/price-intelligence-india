"""Stable idempotency keys for collection jobs.

Strategy
--------
Each logical collection run is identified by a key of the form:

    {job_type}|{retailer_id}|{canonical_scope}

`canonical_scope` is derived only from the caller-supplied logical parameters (search query,
category, limit, optional SKU list). It does **not** include wall-clock time, so repeating the
same logical job — a Celery retry, a duplicate enqueue, an operator re-run with the same
arguments — resolves to the same `CollectionJob` row.

Effects:
- Job rows: unique constraint on `idempotency_key`; a completed SUCCESS/PARTIAL_SUCCESS job is
  returned as-is and is not executed again.
- Products / listings: upserted on `(retailer, retailer_sku)` and identifier uniqueness already
  enforced by Phase 1.
- Prices / availability: `PriceSnapshot` uniqueness on `(retailer_product, observed_at, seller)`
  prevents duplicate observations for the same instant; a skipped re-run does not insert more.
- Sale events: inferred windows are matched on name, dates, type, source, and scope before insert.

A *new* logical run (different query, different SKU set, or an explicit `run_key`) gets a new
key and is a new job. Failed jobs with the same key are retried in place rather than duplicated.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence

from app.domain.enums import CollectionJobType

_KEY_MAX_LENGTH = 512


def build_idempotency_key(
    job_type: CollectionJobType,
    retailer_id: str,
    *,
    scope: Mapping[str, object] | None = None,
    run_key: str | None = None,
) -> str:
    """Return a stable, length-bounded idempotency key."""
    canonical = _canonical_scope(scope)
    if run_key:
        token = _safe_token(run_key)
        canonical = f"{canonical}|run={token}" if canonical else f"run={token}"
    raw = f"{job_type.value}|{retailer_id}|{canonical}"
    if len(raw) <= _KEY_MAX_LENGTH:
        return raw
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    prefix = f"{job_type.value}|{retailer_id}|"
    return f"{prefix}{digest}"[:_KEY_MAX_LENGTH]


def _canonical_scope(scope: Mapping[str, object] | None) -> str:
    if not scope:
        return "*"
    items: dict[str, object] = {}
    for key in sorted(scope):
        value = scope[key]
        if value is None or value == "":
            continue
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            items[key] = sorted(str(item) for item in value)
        else:
            items[key] = value
    if not items:
        return "*"
    return json.dumps(items, sort_keys=True, default=str, separators=(",", ":"))


def _safe_token(value: str) -> str:
    return value.strip().replace("|", "/")[:200]
