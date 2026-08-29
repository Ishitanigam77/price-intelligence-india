"""Chronological train/validation/test splitting."""

from datetime import timedelta
from pathlib import Path

from ml.enums import PredictionStatus
from ml.training.dataset import build_labeled_examples
from ml.training.split import chronological_split
from tests.unit.ml.helpers import ANCHOR, engineer, fixture_catalog, ml_config, observation


def _tiny_examples(count: int):
    points, events = fixture_catalog(listing_count=2, sale_count=count)
    return build_labeled_examples(
        points, events, engineer=engineer(), config=ml_config(min_target_observations=1)
    )


def test_split_is_ordered_by_prediction_timestamp() -> None:
    examples = _tiny_examples(12)
    result = chronological_split(
        examples,
        ml_config(min_train_rows=8, min_validation_rows=2, min_test_rows=2),
    )
    assert not isinstance(result, type(examples))  # SplitAssignment, not the tuple
    from ml.types import SplitAssignment, TrainingResult

    assert isinstance(result, SplitAssignment)
    assert not isinstance(result, TrainingResult)
    assert max(item.features.as_of for item in result.train) <= min(
        item.features.as_of for item in result.validation
    )
    assert max(item.features.as_of for item in result.validation) <= min(
        item.features.as_of for item in result.test
    )
    assert result.train_as_of_end is not None
    assert result.validation_as_of_start is not None
    assert result.test_as_of_start is not None
    assert result.train_as_of_end <= result.validation_as_of_start
    assert result.validation_as_of_end <= result.test_as_of_start


def test_split_does_not_use_random_assignment() -> None:
    source = Path(__file__).resolve().parents[4] / "ml" / "training" / "split.py"
    text = source.read_text(encoding="utf-8")
    forbidden = ("random.shuffle", "train_test_split", "np.random", "sklearn.model_selection")
    for token in forbidden:
        assert token not in text
    first = chronological_split(
        _tiny_examples(12),
        ml_config(min_train_rows=8, min_validation_rows=2, min_test_rows=2),
    )
    second = chronological_split(
        tuple(reversed(_tiny_examples(12))),
        ml_config(min_train_rows=8, min_validation_rows=2, min_test_rows=2),
    )
    from ml.types import SplitAssignment

    assert isinstance(first, SplitAssignment)
    assert isinstance(second, SplitAssignment)
    assert [item.features.as_of for item in first.train] == [
        item.features.as_of for item in second.train
    ]


def test_too_few_rows_returns_insufficient_data() -> None:
    from tests.unit.ml.helpers import event_record, seed_ids

    sale = event_record(start_date=ANCHOR + timedelta(days=2), end_date=ANCHOR + timedelta(days=5))
    listing_id, variant_id = seed_ids()
    point = observation(
        listing_id=listing_id,
        variant_id=variant_id,
        displayed_price="10.00",
        effective_price="10.00",
        observed_at=ANCHOR,
    )
    during = observation(
        listing_id=listing_id,
        variant_id=variant_id,
        displayed_price="8.00",
        effective_price="8.00",
        observed_at=sale.start_date + timedelta(days=1),
    )
    examples = build_labeled_examples(
        [point, during], [sale], engineer=engineer(), config=ml_config()
    )
    result = chronological_split(examples, ml_config(min_train_rows=20))
    from ml.types import TrainingResult

    assert isinstance(result, TrainingResult)
    assert result.status is PredictionStatus.INSUFFICIENT_DATA
    assert result.insufficient is not None
