"""Sale-family identity derived from persisted SaleEvent records.

Families group repeated occurrences of the same campaign pattern (normalized name +
scope) so multi-year mapping does not depend on copying last year's raw dates.
Inferred detections that only differ by a date stamp collapse into one family.
"""

from __future__ import annotations

import re
import uuid
from collections import defaultdict
from collections.abc import Sequence

from app.sales.models import SaleEventRecord

_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_DETECTED = re.compile(
    r"^detected\s+(retailer|category|brand)\s+sale$",
    re.IGNORECASE,
)
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_family_name(name: str) -> str:
    """Strip years and ISO dates so 'Sale 2024' and 'Sale 2025' share a family."""
    text = name.strip().lower()
    text = _ISO_DATE.sub(" ", text)
    text = _YEAR.sub(" ", text)
    text = _NON_ALNUM.sub("-", text).strip("-")
    if not text:
        return "unnamed"
    if _DETECTED.match(text.replace("-", " ")):
        return "inferred-sale"
    return text


def family_key(event: SaleEventRecord) -> str:
    """Stable key: scope + normalized name. Catalogue-wide events use `catalogue`."""
    scope = event.retailer_id or event.brand_id or event.category_id
    scope_part = str(scope) if scope is not None else "catalogue"
    return f"{scope_part}:{normalize_family_name(event.name)}"


def group_by_family(
    events: Sequence[SaleEventRecord],
) -> dict[str, tuple[SaleEventRecord, ...]]:
    grouped: dict[str, list[SaleEventRecord]] = defaultdict(list)
    for event in events:
        grouped[family_key(event)].append(event)
    return {
        key: tuple(sorted(items, key=lambda item: (item.start_date, item.id)))
        for key, items in grouped.items()
    }


def family_retailer_id(events: Sequence[SaleEventRecord]) -> uuid.UUID | None:
    retailers = {item.retailer_id for item in events}
    retailers.discard(None)
    if len(retailers) == 1:
        return next(iter(retailers))
    return None
