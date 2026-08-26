"""Evaluation dataset: precision, recall, false positives, false negatives."""

from app.matching.evaluation import evaluate_predictions
from tests.unit.matching.dataset import load_evaluation_cases
from tests.unit.matching.helpers import make_engine

REQUIRED_SCENARIO_IDS = {
    "identical-products-different-titles",
    "retailer-naming-differences-gtin-vs-mpn",
    "spelling-differences",
    "different-storage",
    "different-ram",
    "different-colors",
    "different-generations",
    "different-sizes-capacities",
    "accessory-vs-main-product",
    "conflicting-gtin-same-title",
    "identifier-match-variant-conflict-needs-review",
    "missing-identifiers-ambiguous-generic-titles",
    "exact-upc-ean-equivalent",
}


def test_evaluation_dataset_covers_required_scenarios() -> None:
    cases = load_evaluation_cases()
    ids = {case.pair_id for case in cases}
    missing = REQUIRED_SCENARIO_IDS - ids
    assert missing == set()
    expected_labels = {case.expected.value for case in cases}
    assert "SAME_PRODUCT" in expected_labels
    assert "DIFFERENT_PRODUCT" in expected_labels
    assert "NEEDS_REVIEW" in expected_labels
    assert "POSSIBLE_MATCH" in expected_labels


def test_evaluation_metrics_and_no_false_merges() -> None:
    engine = make_engine()
    cases = load_evaluation_cases()
    rows = [(case.pair_id, case.expected, engine.compare(case.left, case.right)) for case in cases]
    report = evaluate_predictions(rows)

    mismatches = [
        (item.pair_id, item.expected.value, item.predicted.value)
        for item in report.outcomes
        if item.expected != item.predicted
    ]
    false_merges = [
        item.pair_id
        for item in report.outcomes
        if item.predicted.value == "SAME_PRODUCT" and item.expected.value != "SAME_PRODUCT"
    ]

    print(
        "matching evaluation: "
        f"precision={report.precision} recall={report.recall} "
        f"false_positives={report.false_positives} false_negatives={report.false_negatives} "
        f"exact_accuracy={report.exact_classification_accuracy} "
        f"mismatches={mismatches}"
    )

    assert false_merges == [], f"false SAME_PRODUCT merges: {false_merges}"
    assert report.false_positives == 0
    assert report.precision == 1.0
    assert report.recall >= 0.8
    assert report.true_positives >= 5
    payload = report.as_dict()
    assert payload["precision"] == report.precision
    assert payload["recall"] == report.recall
    assert payload["false_positives"] == 0
    assert payload["false_negatives"] == report.false_negatives
