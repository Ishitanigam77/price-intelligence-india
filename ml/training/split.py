"""Strict chronological train / validation / test splitting.

Primary evaluation never uses random row shuffling. Examples are ordered by prediction
timestamp (`as_of`). Unique timestamps are cut into earlier → later contiguous ranges so
every validation timestamp is at or after every training timestamp, and every test
timestamp is at or after every validation timestamp.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from ml.config import MLConfig, get_ml_config
from ml.enums import InsufficientDataReason, PredictionStatus
from ml.types import InsufficientData, LabeledExample, SplitAssignment, TrainingResult


def _range(examples: Sequence[LabeledExample]) -> tuple[datetime | None, datetime | None]:
    if not examples:
        return None, None
    stamps = [item.features.as_of for item in examples]
    return min(stamps), max(stamps)


def _insufficient(code: InsufficientDataReason, reason: str, size: int) -> TrainingResult:
    return TrainingResult(
        status=PredictionStatus.INSUFFICIENT_DATA,
        insufficient=InsufficientData(code=code, reason=reason),
        training_data_size=size,
    )


def chronological_split(
    examples: Sequence[LabeledExample],
    config: MLConfig | None = None,
) -> SplitAssignment | TrainingResult:
    """Split by prediction time. Returns INSUFFICIENT_DATA when any fold is too small."""
    cfg = config if config is not None else get_ml_config()
    ordered = sorted(
        examples,
        key=lambda item: (item.features.as_of, item.target_event_id, item.listing_key),
    )
    n = len(ordered)
    if n == 0:
        return _insufficient(
            InsufficientDataReason.NO_LABELED_EXAMPLES,
            "No labeled examples could be built from stored observations and sale events. "
            "Historical prices are not fabricated to force training.",
            0,
        )

    unique_times = sorted({item.features.as_of for item in ordered})
    n_times = len(unique_times)
    train_time_end = max(1, int(n_times * cfg.train_fraction))
    val_time_end = max(
        train_time_end + 1,
        int(n_times * (cfg.train_fraction + cfg.validation_fraction)),
    )
    if val_time_end >= n_times:
        val_time_end = n_times - 1
    if train_time_end >= val_time_end:
        train_time_end = max(1, val_time_end - 1)

    train_cutoff = unique_times[train_time_end - 1]
    val_cutoff = unique_times[val_time_end - 1] if val_time_end > 0 else unique_times[0]

    train = tuple(item for item in ordered if item.features.as_of <= train_cutoff)
    validation = tuple(item for item in ordered if train_cutoff < item.features.as_of <= val_cutoff)
    test = tuple(item for item in ordered if item.features.as_of > val_cutoff)

    if len(train) < cfg.min_train_rows:
        return _insufficient(
            InsufficientDataReason.BELOW_MINIMUM_TRAIN_ROWS,
            (
                f"Chronological training split has {len(train)} row(s); "
                f"{cfg.min_train_rows} are required. Data is not fabricated to fill the gap."
            ),
            n,
        )
    if len(validation) < cfg.min_validation_rows:
        return _insufficient(
            InsufficientDataReason.BELOW_MINIMUM_VALIDATION_ROWS,
            (
                f"Chronological validation split has {len(validation)} row(s); "
                f"{cfg.min_validation_rows} are required. Data is not fabricated to fill the gap."
            ),
            n,
        )
    if len(test) < cfg.min_test_rows:
        return _insufficient(
            InsufficientDataReason.BELOW_MINIMUM_TEST_ROWS,
            (
                f"Chronological test split has {len(test)} row(s); "
                f"{cfg.min_test_rows} are required. Data is not fabricated to fill the gap."
            ),
            n,
        )

    train_start, train_end = _range(train)
    val_start, val_end = _range(validation)
    test_start, test_end = _range(test)
    return SplitAssignment(
        train=train,
        validation=validation,
        test=test,
        train_as_of_start=train_start,
        train_as_of_end=train_end,
        validation_as_of_start=val_start,
        validation_as_of_end=val_end,
        test_as_of_start=test_start,
        test_as_of_end=test_end,
    )
