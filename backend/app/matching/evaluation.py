"""Evaluation helpers: precision, recall, false positives, false negatives.

The positive class is `SAME_PRODUCT` — a false positive is a dangerous merge of listings that
are not the same variant. Other classifications are treated as "not merged".
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.matching.enums import MatchClassification
from app.matching.models import MatchResult

POSITIVE = MatchClassification.SAME_PRODUCT


@dataclass(frozen=True)
class EvaluationPairOutcome:
    pair_id: str
    expected: MatchClassification
    predicted: MatchClassification
    match_score: float
    match_method: str
    match_confidence: str


@dataclass(frozen=True)
class EvaluationReport:
    outcomes: tuple[EvaluationPairOutcome, ...]
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    precision: float
    recall: float
    exact_classification_accuracy: float

    def as_dict(self) -> dict[str, object]:
        return {
            "pair_count": len(self.outcomes),
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "true_negatives": self.true_negatives,
            "precision": self.precision,
            "recall": self.recall,
            "exact_classification_accuracy": self.exact_classification_accuracy,
            "outcomes": [
                {
                    "pair_id": item.pair_id,
                    "expected": item.expected.value,
                    "predicted": item.predicted.value,
                    "match_score": item.match_score,
                    "match_method": item.match_method,
                    "match_confidence": item.match_confidence,
                }
                for item in self.outcomes
            ],
        }


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def evaluate_predictions(
    rows: Sequence[tuple[str, MatchClassification, MatchResult]],
) -> EvaluationReport:
    """`rows` is `(pair_id, expected_classification, predicted_result)`."""
    outcomes: list[EvaluationPairOutcome] = []
    true_positives = 0
    false_positives = 0
    false_negatives = 0
    true_negatives = 0
    exact = 0
    for pair_id, expected, result in rows:
        predicted = result.classification
        outcomes.append(
            EvaluationPairOutcome(
                pair_id=pair_id,
                expected=expected,
                predicted=predicted,
                match_score=result.match_score,
                match_method=result.match_method.value,
                match_confidence=result.match_confidence.value,
            )
        )
        if predicted is expected:
            exact += 1
        expected_positive = expected is POSITIVE
        predicted_positive = predicted is POSITIVE
        if expected_positive and predicted_positive:
            true_positives += 1
        elif predicted_positive and not expected_positive:
            false_positives += 1
        elif expected_positive and not predicted_positive:
            false_negatives += 1
        else:
            true_negatives += 1
    return EvaluationReport(
        outcomes=tuple(outcomes),
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        true_negatives=true_negatives,
        precision=_ratio(true_positives, true_positives + false_positives),
        recall=_ratio(true_positives, true_positives + false_negatives),
        exact_classification_accuracy=_ratio(exact, len(rows)),
    )
