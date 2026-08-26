"""Retailer-agnostic matching inputs and outputs.

`MatchCandidate` is the only shape the engine compares. It can be built from the Phase 2
`NormalizedProduct` boundary model; it never carries retailer-native payloads.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.enums import ProductIdentifierType, SourceType
from app.matching.enums import (
    MatchClassification,
    MatchConfidence,
    MatchIdentifierType,
    MatchMethod,
    MatchStageName,
)
from app.retailer_adapters.base.models import NormalizedProduct, ProductIdentifierValue

_IDENTIFIER_TYPE_MAP: dict[ProductIdentifierType, MatchIdentifierType] = {
    ProductIdentifierType.GTIN: MatchIdentifierType.GTIN,
    ProductIdentifierType.EAN: MatchIdentifierType.EAN,
    ProductIdentifierType.UPC: MatchIdentifierType.UPC,
    ProductIdentifierType.ISBN: MatchIdentifierType.ISBN,
    ProductIdentifierType.MPN: MatchIdentifierType.MPN,
    ProductIdentifierType.OTHER: MatchIdentifierType.OTHER,
}

_MODEL_ATTRIBUTE_KEYS = frozenset({"model_number", "model-number", "model_no", "modelno"})


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class MatchIdentifier(_FrozenModel):
    """One typed identifier on a listing being compared."""

    identifier_type: MatchIdentifierType
    value: str = Field(min_length=1, max_length=200)

    @field_validator("value")
    @classmethod
    def _strip(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Identifier value must not be blank.")
        return stripped


class ListingProvenance(_FrozenModel):
    """Retailer/source fields preserved on every comparison result."""

    retailer_id: str | None = None
    retailer_sku: str | None = None
    source_url: str | None = None
    source_type: str | None = None


class MatchCandidate(_FrozenModel):
    """One listing (or catalog variant) as the matching engine sees it."""

    retailer_id: str | None = None
    retailer_sku: str | None = None
    source_url: str | None = None
    source_type: SourceType | str | None = None
    title: str = Field(min_length=1, max_length=1000)
    brand_name: str | None = Field(default=None, max_length=200)
    brand_slug: str | None = None
    category_slug: str | None = None
    identifiers: tuple[MatchIdentifier, ...] = ()
    variant_attributes: Mapping[str, str] = Field(default_factory=dict)

    @field_validator("title")
    @classmethod
    def _strip_title(cls, value: str) -> str:
        stripped = " ".join(value.split())
        if not stripped:
            raise ValueError("Match candidate title must not be blank.")
        return stripped

    @field_validator("variant_attributes")
    @classmethod
    def _copy_attributes(cls, value: Mapping[str, str]) -> dict[str, str]:
        return {str(key): str(val) for key, val in value.items() if str(key) and str(val)}

    def provenance(self) -> ListingProvenance:
        source_type = (
            self.source_type.value if isinstance(self.source_type, SourceType) else self.source_type
        )
        return ListingProvenance(
            retailer_id=self.retailer_id,
            retailer_sku=self.retailer_sku,
            source_url=self.source_url,
            source_type=source_type,
        )

    @classmethod
    def from_normalized_product(cls, product: NormalizedProduct) -> MatchCandidate:
        """Lift a Phase 2/4 `NormalizedProduct` into a matching candidate.

        Does not change adapter behaviour; this is a read-only projection.
        """
        identifiers = [
            MatchIdentifier(
                identifier_type=_IDENTIFIER_TYPE_MAP[item.identifier_type],
                value=item.value,
            )
            for item in product.identifiers
        ]
        identifiers.extend(_model_identifiers_from_attributes(product.variant_attributes))
        return cls(
            retailer_id=product.retailer_id,
            retailer_sku=product.retailer_sku,
            source_url=product.source_url,
            source_type=product.source_type,
            title=product.normalized_title,
            brand_name=product.brand_name,
            brand_slug=product.brand_slug,
            category_slug=product.category_slug,
            identifiers=tuple(identifiers),
            variant_attributes=dict(product.variant_attributes),
        )

    @classmethod
    def from_identifier_values(
        cls,
        *,
        title: str,
        identifiers: tuple[ProductIdentifierValue, ...] = (),
        variant_attributes: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> MatchCandidate:
        """Build a candidate from Phase 1 identifier values plus free-form fields."""
        mapped = tuple(
            MatchIdentifier(
                identifier_type=_IDENTIFIER_TYPE_MAP[item.identifier_type],
                value=item.value,
            )
            for item in identifiers
        )
        attrs = dict(variant_attributes or {})
        extra_model = _model_identifiers_from_attributes(attrs)
        return cls(
            title=title,
            identifiers=mapped + extra_model,
            variant_attributes=attrs,
            **kwargs,
        )


class StageEvidence(_FrozenModel):
    """What one pipeline stage observed, including whether it was applicable."""

    stage: MatchStageName
    applicable: bool
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    summary: str
    details: Mapping[str, Any] = Field(default_factory=dict)


class MatchResult(_FrozenModel):
    """Outcome of comparing two listings."""

    classification: MatchClassification
    match_score: float = Field(ge=0.0, le=1.0)
    match_method: MatchMethod
    match_confidence: MatchConfidence
    explanation: str
    contributing_stages: tuple[MatchStageName, ...]
    evidence: tuple[StageEvidence, ...]
    left: ListingProvenance
    right: ListingProvenance

    def evidence_for(self, stage: MatchStageName) -> StageEvidence | None:
        for item in self.evidence:
            if item.stage is stage:
                return item
        return None


def _model_identifiers_from_attributes(
    attributes: Mapping[str, str],
) -> tuple[MatchIdentifier, ...]:
    found: list[MatchIdentifier] = []
    seen: set[str] = set()
    for key, value in attributes.items():
        if key.strip().lower() not in _MODEL_ATTRIBUTE_KEYS:
            continue
        stripped = str(value).strip()
        if stripped and stripped.lower() not in seen:
            seen.add(stripped.lower())
            found.append(
                MatchIdentifier(identifier_type=MatchIdentifierType.MODEL_NUMBER, value=stripped)
            )
    return tuple(found)
