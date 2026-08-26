"""Load the fictional matching evaluation dataset."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.matching.enums import MatchClassification, MatchIdentifierType
from app.matching.models import MatchCandidate, MatchIdentifier

DATASET_PATH = Path(__file__).resolve().parent / "fixtures" / "evaluation_dataset.json"


@dataclass(frozen=True)
class EvaluationCase:
    pair_id: str
    expected: MatchClassification
    left: MatchCandidate
    right: MatchCandidate


def _candidate(payload: dict[str, object]) -> MatchCandidate:
    raw_identifiers = payload.get("identifiers") or []
    identifiers = tuple(
        MatchIdentifier(
            identifier_type=MatchIdentifierType(str(item["identifier_type"])),
            value=str(item["value"]),
        )
        for item in raw_identifiers  # type: ignore[union-attr]
    )
    brand_name = payload.get("brand_name")
    brand_slug = payload.get("brand_slug")
    return MatchCandidate(
        retailer_id=str(payload["retailer_id"]) if payload.get("retailer_id") else None,
        retailer_sku=str(payload["retailer_sku"]) if payload.get("retailer_sku") else None,
        source_url=str(payload["source_url"]) if payload.get("source_url") else None,
        title=str(payload["title"]),
        brand_name=str(brand_name) if brand_name else None,
        brand_slug=str(brand_slug) if brand_slug else None,
        category_slug=str(payload["category_slug"]) if payload.get("category_slug") else None,
        identifiers=identifiers,
        variant_attributes=dict(payload.get("variant_attributes") or {}),  # type: ignore[arg-type]
    )


def load_evaluation_cases(path: Path | None = None) -> tuple[EvaluationCase, ...]:
    dataset = json.loads((path or DATASET_PATH).read_text(encoding="utf-8"))
    cases: list[EvaluationCase] = []
    for row in dataset["pairs"]:
        cases.append(
            EvaluationCase(
                pair_id=str(row["id"]),
                expected=MatchClassification(str(row["expected"])),
                left=_candidate(row["left"]),
                right=_candidate(row["right"]),
            )
        )
    return tuple(cases)
