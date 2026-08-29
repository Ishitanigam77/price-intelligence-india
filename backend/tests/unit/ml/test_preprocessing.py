"""Preprocessor: train-only encoding, unknown categories become missing."""

import math

import numpy as np

from ml.preprocessing.encode import FeaturePreprocessor
from ml.training.dataset import build_labeled_examples
from tests.unit.ml.helpers import engineer, fixture_catalog, ml_config


def test_unknown_category_becomes_nan_not_a_future_code() -> None:
    points, events = fixture_catalog(listing_count=4, sale_count=6)
    examples = build_labeled_examples(
        points, events, engineer=engineer(), config=ml_config(min_target_observations=1)
    )
    assert len(examples) >= 4
    train = examples[: max(1, len(examples) // 2)]
    held_out = examples[max(1, len(examples) // 2) :]
    preprocessor = FeaturePreprocessor().fit(train)
    matrix = preprocessor.transform_features([held_out[0].features])
    assert matrix.shape[1] == len(preprocessor.feature_names)
    # Fitting only on train means a retailer/listing unseen in train is NaN, not a new id.
    unseen = held_out[0].features.model_copy(
        update={
            "categorical": {
                **held_out[0].features.categorical,
                "retailer_id": "00000000-0000-0000-0000-ffffffffffff",
            }
        }
    )
    row = preprocessor.transform_features([unseen])[0]
    retailer_index = preprocessor.feature_names.index("cat_retailer_id")
    assert math.isnan(float(row[retailer_index]))
    features, targets = preprocessor.transform(train)
    assert features.shape[0] == len(train)
    assert targets.shape[0] == len(train)
    assert not np.any(np.isnan(targets))
