"""Pipeline stages as injectable units.

The engine runs these in order. A custom stage can be supplied as long as it exposes
`name` and `evaluate(left, right) -> StageEvidence`.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.matching.attributes import compare_attributes, merge_attributes
from app.matching.config import MatchingConfig
from app.matching.embeddings import EmbeddingProvider
from app.matching.enums import MatchStageName
from app.matching.identifiers import compare_identifiers
from app.matching.models import MatchCandidate, StageEvidence
from app.matching.titles import embedding_document, title_similarity


@runtime_checkable
class MatchStage(Protocol):
    """One comparison stage in the matching pipeline."""

    @property
    def name(self) -> MatchStageName: ...

    def evaluate(self, left: MatchCandidate, right: MatchCandidate) -> StageEvidence: ...


class ExactIdentifierStage:
    """Stage 1 — exact identifiers after format normalization."""

    def __init__(self, config: MatchingConfig) -> None:
        self._config = config

    @property
    def name(self) -> MatchStageName:
        return MatchStageName.EXACT_IDENTIFIERS

    def evaluate(self, left: MatchCandidate, right: MatchCandidate) -> StageEvidence:
        details = compare_identifiers(left, right)
        matches = details["matches"]
        conflicts = details["conflicts"]
        applicable = bool(matches) or bool(conflicts)
        if conflicts:
            score = 0.0
            summary = (
                "Conflicting identifiers in " + ", ".join(item["family"] for item in conflicts)  # type: ignore[index]
            )
        elif matches:
            score = 1.0
            families = ", ".join(item["family"] for item in matches)  # type: ignore[index]
            summary = f"Exact identifier match after normalization ({families})"
        else:
            score = None
            summary = "No comparable identifiers on both listings (missing is not a match)"
        return StageEvidence(
            stage=self.name,
            applicable=applicable,
            score=score,
            summary=summary,
            details=details,
        )


class NormalizedAttributeStage:
    """Stage 2 — brand / model / variant attributes."""

    def __init__(self, config: MatchingConfig) -> None:
        self._config = config

    @property
    def name(self) -> MatchStageName:
        return MatchStageName.NORMALIZED_ATTRIBUTES

    def evaluate(self, left: MatchCandidate, right: MatchCandidate) -> StageEvidence:
        details = compare_attributes(left, right, self._config)
        variant_conflicts = details["variant_conflicts"]
        accessory = details["accessory_mismatch"]
        agreements = details["agreements"]
        overlapping = details["overlapping_variant_keys"]
        brand_match = details["brand_match"]
        model_match = details["model_match"]
        applicable = True
        if accessory:
            score = 0.0
            summary = "Accessory listing compared with a primary product"
        elif variant_conflicts:
            keys = ", ".join(item["key"] for item in variant_conflicts)  # type: ignore[index]
            score = 0.0
            summary = f"Variant attributes conflict ({keys})"
        elif details["model_conflict"]:
            score = 0.05
            summary = (
                "Derived model hints disagree "
                f"({details['left_model_hint']!r} vs {details['right_model_hint']!r})"
            )
        elif brand_match is False:
            score = 0.1
            summary = "Brands do not match"
        else:
            overlap_count = len(overlapping)  # type: ignore[arg-type]
            variant_agreements = [
                key
                for key in agreements
                if key in overlapping  # type: ignore[operator]
            ]
            agree_ratio = (len(variant_agreements) / overlap_count) if overlap_count else 0.0
            brand_component = 1.0 if brand_match else (0.5 if brand_match is None else 0.0)
            model_component = 1.0 if model_match else (0.5 if model_match is None else 0.0)
            score = min(
                1.0,
                round(0.35 * brand_component + 0.35 * model_component + 0.30 * agree_ratio, 4),
            )
            if brand_match and model_match and not variant_conflicts:
                summary = "Brand, model, and overlapping variant attributes agree"
            elif brand_match and agree_ratio == 1.0 and overlap_count:
                summary = "Brand and overlapping variant attributes agree"
            else:
                summary = "Partial structured-attribute agreement"
        return StageEvidence(
            stage=self.name,
            applicable=applicable,
            score=score,
            summary=summary,
            details=details,
        )


class TitleTokenStage:
    """Stage 3 — normalized title / token similarity."""

    def __init__(self, config: MatchingConfig) -> None:
        self._config = config

    @property
    def name(self) -> MatchStageName:
        return MatchStageName.TITLE_TOKEN_SIMILARITY

    def evaluate(self, left: MatchCandidate, right: MatchCandidate) -> StageEvidence:
        details = title_similarity(left.title, right.title, self._config)
        score = float(details["score"])  # type: ignore[arg-type]
        return StageEvidence(
            stage=self.name,
            applicable=True,
            score=score,
            summary=f"Normalized title token similarity {score:.3f}",
            details=details,
        )


class EmbeddingSimilarityStage:
    """Stage 4 — cosine similarity of configurable embeddings."""

    def __init__(self, config: MatchingConfig, provider: EmbeddingProvider) -> None:
        self._config = config
        self._provider = provider

    @property
    def name(self) -> MatchStageName:
        return MatchStageName.EMBEDDING_SIMILARITY

    def evaluate(self, left: MatchCandidate, right: MatchCandidate) -> StageEvidence:
        left_doc = embedding_document(left.title, left.brand_name, merge_attributes(left))
        right_doc = embedding_document(right.title, right.brand_name, merge_attributes(right))
        score = round(self._provider.similarity(left_doc, right_doc), 4)
        details = {
            "cosine_similarity": score,
            "backend": self._provider.name,
            "left_document": left_doc,
            "right_document": right_doc,
        }
        return StageEvidence(
            stage=self.name,
            applicable=True,
            score=score,
            summary=(
                f"Embedding cosine similarity {score:.3f} via {self._provider.name} "
                "(supporting evidence only)"
            ),
            details=details,
        )


def default_stages(config: MatchingConfig, provider: EmbeddingProvider) -> tuple[MatchStage, ...]:
    return (
        ExactIdentifierStage(config),
        NormalizedAttributeStage(config),
        TitleTokenStage(config),
        EmbeddingSimilarityStage(config, provider),
    )
