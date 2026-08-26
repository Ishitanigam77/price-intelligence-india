"""Combine stage evidence into a classification.

Safety rules implemented here:

- Title similarity alone never yields `SAME_PRODUCT`.
- Embeddings never override identifier conflicts, variant conflicts, or accessory mismatches.
- Conflicting strong identifiers are not ignored.
- Missing identifiers are not treated as `DIFFERENT_PRODUCT` by themselves.
- Ambiguous cases become `POSSIBLE_MATCH` or `NEEDS_REVIEW` rather than a forced merge.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.matching.config import MatchingConfig
from app.matching.enums import (
    MatchClassification,
    MatchConfidence,
    MatchMethod,
    MatchStageName,
)
from app.matching.models import ListingProvenance, MatchResult, StageEvidence


def weighted_score(evidence: Sequence[StageEvidence], weights: Mapping[str, float]) -> float:
    """Average applicable stage scores, renormalizing weights when a stage is inapplicable."""
    used: list[tuple[float, float]] = []
    for item in evidence:
        if item.score is None or not item.applicable:
            continue
        weight = weights.get(item.stage.value, 0.0)
        if weight <= 0.0:
            continue
        used.append((item.score, weight))
    if not used:
        return 0.0
    total_weight = sum(weight for _, weight in used)
    if total_weight <= 0.0:
        return 0.0
    combined = sum(score * weight for score, weight in used) / total_weight
    return round(min(1.0, max(0.0, combined)), 4)


def _stage_map(evidence: Sequence[StageEvidence]) -> dict[MatchStageName, StageEvidence]:
    return {item.stage: item for item in evidence}


def _contributing(evidence: Sequence[StageEvidence]) -> tuple[MatchStageName, ...]:
    return tuple(item.stage for item in evidence if item.applicable)


def decide(
    *,
    evidence: Sequence[StageEvidence],
    config: MatchingConfig,
    left: ListingProvenance,
    right: ListingProvenance,
) -> MatchResult:
    by_stage = _stage_map(evidence)
    identifiers = by_stage[MatchStageName.EXACT_IDENTIFIERS]
    attributes = by_stage[MatchStageName.NORMALIZED_ATTRIBUTES]
    title = by_stage[MatchStageName.TITLE_TOKEN_SIMILARITY]
    embedding = by_stage[MatchStageName.EMBEDDING_SIMILARITY]

    id_details = dict(identifiers.details)
    attr_details = dict(attributes.details)
    identifier_matches = list(id_details.get("matches") or [])
    identifier_conflicts = list(id_details.get("conflicts") or [])
    variant_conflicts = list(attr_details.get("variant_conflicts") or [])
    accessory_mismatch = bool(attr_details.get("accessory_mismatch"))
    brand_match = attr_details.get("brand_match")
    model_match = attr_details.get("model_match")
    model_conflict = bool(attr_details.get("model_conflict"))
    title_score = title.score if title.score is not None else 0.0
    embedding_score = embedding.score if embedding.score is not None else 0.0
    composite = weighted_score(evidence, config.stage_weights)

    contributing = _contributing(evidence)

    def _result(
        classification: MatchClassification,
        method: MatchMethod,
        confidence: MatchConfidence,
        *,
        score: float,
        explanation: str,
    ) -> MatchResult:
        return MatchResult(
            classification=classification,
            match_score=round(min(1.0, max(0.0, score)), 4),
            match_method=method,
            match_confidence=confidence,
            explanation=explanation,
            contributing_stages=contributing,
            evidence=tuple(evidence),
            left=left,
            right=right,
        )

    if identifier_conflicts:
        families = ", ".join(item["family"] for item in identifier_conflicts)
        return _result(
            MatchClassification.DIFFERENT_PRODUCT,
            MatchMethod.EXACT_IDENTIFIER,
            MatchConfidence.HIGH,
            score=min(composite, 0.2),
            explanation=(
                f"DIFFERENT_PRODUCT because strong identifiers conflict after normalization "
                f"({families}). Title similarity {title_score:.3f} and embedding cosine "
                f"{embedding_score:.3f} are supporting evidence only and do not override this."
            ),
        )

    if identifier_matches and variant_conflicts:
        keys = ", ".join(item["key"] for item in variant_conflicts)
        families = ", ".join(item["family"] for item in identifier_matches)
        return _result(
            MatchClassification.NEEDS_REVIEW,
            MatchMethod.CONFLICTING_EVIDENCE,
            MatchConfidence.MEDIUM,
            score=min(max(composite, 0.45), 0.7),
            explanation=(
                f"NEEDS_REVIEW because identifiers match ({families}) but variant attributes "
                f"conflict ({keys}). Neither signal is ignored."
            ),
        )

    if identifier_matches and brand_match is False:
        families = ", ".join(item["family"] for item in identifier_matches)
        return _result(
            MatchClassification.NEEDS_REVIEW,
            MatchMethod.CONFLICTING_EVIDENCE,
            MatchConfidence.MEDIUM,
            score=min(max(composite, 0.45), 0.7),
            explanation=(
                f"NEEDS_REVIEW because identifiers match ({families}) but brands disagree. "
                "Manual review is required rather than a forced merge."
            ),
        )

    if accessory_mismatch:
        return _result(
            MatchClassification.DIFFERENT_PRODUCT,
            MatchMethod.NORMALIZED_ATTRIBUTES,
            MatchConfidence.HIGH,
            score=min(composite, 0.25),
            explanation=(
                "DIFFERENT_PRODUCT because one listing is an accessory and the other is a "
                f"primary product. Title similarity {title_score:.3f} cannot merge them."
            ),
        )

    if variant_conflicts:
        keys = ", ".join(item["key"] for item in variant_conflicts)
        return _result(
            MatchClassification.DIFFERENT_PRODUCT,
            MatchMethod.NORMALIZED_ATTRIBUTES,
            MatchConfidence.HIGH,
            score=min(composite, 0.45),
            explanation=(
                f"DIFFERENT_PRODUCT because variant attributes conflict ({keys}). "
                "Embeddings and title similarity must not override variant separation."
            ),
        )

    if model_conflict and not identifier_matches:
        return _result(
            MatchClassification.DIFFERENT_PRODUCT,
            MatchMethod.NORMALIZED_ATTRIBUTES,
            MatchConfidence.HIGH,
            score=min(composite, 0.4),
            explanation=(
                "DIFFERENT_PRODUCT because derived model hints disagree "
                f"({attr_details.get('left_model_hint')!r} vs "
                f"{attr_details.get('right_model_hint')!r})."
            ),
        )

    if brand_match is False and not identifier_matches:
        return _result(
            MatchClassification.DIFFERENT_PRODUCT,
            MatchMethod.NORMALIZED_ATTRIBUTES,
            MatchConfidence.HIGH,
            score=min(composite, 0.35),
            explanation=(
                "DIFFERENT_PRODUCT because brands do not match and no shared exact identifier "
                "is present. High title similarity alone is never enough to merge."
            ),
        )

    if identifier_matches:
        families = ", ".join(item["family"] for item in identifier_matches)
        score = max(composite, 0.9)
        return _result(
            MatchClassification.SAME_PRODUCT,
            MatchMethod.EXACT_IDENTIFIER,
            MatchConfidence.HIGH,
            score=score,
            explanation=(
                f"SAME_PRODUCT because exact identifiers match after normalization ({families}). "
                f"{attributes.summary}. Title similarity {title_score:.3f} and embedding cosine "
                f"{embedding_score:.3f} are supporting evidence only."
            ),
        )

    strong_attributes = brand_match is True and model_match is True and not variant_conflicts

    if strong_attributes:
        confidence = (
            MatchConfidence.HIGH
            if title_score >= config.title_medium_threshold
            else MatchConfidence.MEDIUM
        )
        return _result(
            MatchClassification.SAME_PRODUCT,
            MatchMethod.NORMALIZED_ATTRIBUTES,
            confidence,
            score=max(composite, config.same_product_min_score),
            explanation=(
                "SAME_PRODUCT because brand and model agree and overlapping variant attributes "
                f"do not conflict. Title similarity {title_score:.3f} and embedding cosine "
                f"{embedding_score:.3f} support the decision but are not sufficient on their own."
            ),
        )

    # Title and/or embeddings may suggest a relationship, but never SAME_PRODUCT from those
    # stages alone — even when both are high.
    title_and_embed_high = (
        title_score >= config.title_high_threshold
        and embedding_score >= config.embedding_high_threshold
    )
    title_or_embed_medium = (
        title_score >= config.title_medium_threshold
        or embedding_score >= config.embedding_medium_threshold
    )

    if title_and_embed_high and brand_match is True:
        method = MatchMethod.COMBINED
        return _result(
            MatchClassification.POSSIBLE_MATCH,
            method,
            MatchConfidence.MEDIUM,
            score=max(composite, config.possible_match_min_score),
            explanation=(
                f"POSSIBLE_MATCH because brand agrees and title similarity {title_score:.3f} "
                f"plus embedding cosine {embedding_score:.3f} are high, but exact identifiers "
                "and a complete model/variant set are missing so the pair is not merged."
            ),
        )

    if title_and_embed_high and brand_match is None:
        return _result(
            MatchClassification.NEEDS_REVIEW,
            MatchMethod.COMBINED,
            MatchConfidence.LOW,
            score=max(composite, config.needs_review_min_score),
            explanation=(
                f"NEEDS_REVIEW because title similarity {title_score:.3f} and embedding cosine "
                f"{embedding_score:.3f} are high but brand and identifiers are missing. "
                "Title/embeddings alone cannot classify SAME_PRODUCT."
            ),
        )

    if composite >= config.possible_match_min_score and title_or_embed_medium:
        return _result(
            MatchClassification.POSSIBLE_MATCH,
            MatchMethod.COMBINED,
            MatchConfidence.LOW,
            score=composite,
            explanation=(
                f"POSSIBLE_MATCH from combined evidence (score {composite:.3f}: "
                f"{identifiers.summary}; {attributes.summary}; title {title_score:.3f}; "
                f"embedding {embedding_score:.3f}). Not enough for SAME_PRODUCT."
            ),
        )

    if composite >= config.needs_review_min_score:
        return _result(
            MatchClassification.NEEDS_REVIEW,
            MatchMethod.COMBINED,
            MatchConfidence.LOW,
            score=composite,
            explanation=(
                f"NEEDS_REVIEW because the combined score {composite:.3f} is ambiguous: "
                f"{identifiers.summary}; {attributes.summary}."
            ),
        )

    return _result(
        MatchClassification.DIFFERENT_PRODUCT,
        MatchMethod.COMBINED,
        MatchConfidence.MEDIUM,
        score=composite,
        explanation=(
            f"DIFFERENT_PRODUCT because combined evidence is weak (score {composite:.3f}). "
            f"{identifiers.summary}; {attributes.summary}."
        ),
    )
