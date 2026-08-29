"""Enumerations owned by the sale-price prediction pipeline."""

from enum import StrEnum


class PredictionStatus(StrEnum):
    """Outcome of training or inference. Predictions are never implied by a bare number."""

    PREDICTED = "PREDICTED"
    TRAINED = "TRAINED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class InsufficientDataReason(StrEnum):
    """Machine-readable reason a model or prediction was withheld rather than fabricated."""

    NO_LABELED_EXAMPLES = "no_labeled_examples"
    BELOW_MINIMUM_TRAIN_ROWS = "below_minimum_train_rows"
    BELOW_MINIMUM_VALIDATION_ROWS = "below_minimum_validation_rows"
    BELOW_MINIMUM_TEST_ROWS = "below_minimum_test_rows"
    NO_TRAINED_MODEL = "no_trained_model"
    MODEL_NOT_FOUND = "model_not_found"
    NO_CURRENT_PRICE = "no_current_price"
    NO_QUALIFYING_OBSERVATIONS = "no_qualifying_observations"
    FEATURE_VERSION_MISMATCH = "feature_version_mismatch"
    EMPTY_FEATURE_MATRIX = "empty_feature_matrix"


class SplitName(StrEnum):
    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"
