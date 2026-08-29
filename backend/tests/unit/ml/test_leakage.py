"""Leakage-prevention tests: no future observations, no target-as-feature, no inferred peeking."""

from datetime import timedelta
from decimal import Decimal

import numpy as np

from app.domain.enums import SaleEventSource, SaleEventType
from ml.features.availability import (
    event_schedule_known_at,
    observations_available_at,
)
from ml.preprocessing.encode import FeaturePreprocessor, matrix_contains_target
from ml.training.dataset import build_labeled_examples
from tests.unit.ml.helpers import ANCHOR, engineer, event_record, ml_config, observation, seed_ids


def test_observations_available_at_excludes_future_and_same_instant() -> None:
    listing_id, variant_id = seed_ids()
    past = observation(
        listing_id=listing_id,
        variant_id=variant_id,
        displayed_price="10.00",
        effective_price="10.00",
        observed_at=ANCHOR,
    )
    at = observation(
        listing_id=listing_id,
        variant_id=variant_id,
        displayed_price="20.00",
        effective_price="20.00",
        observed_at=ANCHOR + timedelta(days=5),
    )
    future = observation(
        listing_id=listing_id,
        variant_id=variant_id,
        displayed_price="30.00",
        effective_price="30.00",
        observed_at=ANCHOR + timedelta(days=10),
    )
    as_of = ANCHOR + timedelta(days=5)
    available = observations_available_at(
        [past.observation, at.observation, future.observation], as_of=as_of
    )
    assert [point.snapshot_id for point in available] == [past.observation.snapshot_id]
    prices = {point.analysis_price for point in available}
    assert Decimal("20.00") not in prices
    assert Decimal("30.00") not in prices


def test_late_created_observation_is_not_available_even_if_observed_earlier() -> None:
    point = observation(
        displayed_price="77.00",
        effective_price="77.00",
        observed_at=ANCHOR,
        created_at=ANCHOR + timedelta(days=3),
    )
    available = observations_available_at([point.observation], as_of=ANCHOR + timedelta(days=1))
    assert available == ()


def test_future_unique_price_does_not_enter_historical_low() -> None:
    listing_id, variant_id = seed_ids()
    points = [
        observation(
            listing_id=listing_id,
            variant_id=variant_id,
            displayed_price="500.00",
            effective_price="500.00",
            observed_at=ANCHOR,
        ),
        observation(
            listing_id=listing_id,
            variant_id=variant_id,
            displayed_price="1.23",
            effective_price="1.23",
            observed_at=ANCHOR + timedelta(days=30),
        ),
    ]
    vector = engineer().build(points, [], as_of=ANCHOR + timedelta(days=10))
    assert vector is not None
    assert vector.numeric["historical_low"] == 500.0
    assert vector.numeric["current_price"] != 1.23


def test_inferred_sale_is_not_known_before_it_ends() -> None:
    inferred = event_record(
        name="FIXTURE: inferred window",
        start_date=ANCHOR + timedelta(days=10),
        end_date=ANCHOR + timedelta(days=16),
        event_type=SaleEventType.SEASONAL,
        source=SaleEventSource.OBSERVED_PRICE_INFERENCE,
        source_ref="calculated.observed_price_inference",
    )
    assert event_schedule_known_at(inferred, as_of=inferred.start_date) is False
    assert event_schedule_known_at(inferred, as_of=inferred.end_date) is False
    assert event_schedule_known_at(inferred, as_of=inferred.end_date + timedelta(seconds=1)) is True
    point = observation(
        displayed_price="900.00",
        effective_price="900.00",
        observed_at=ANCHOR,
        retailer_id=inferred.retailer_id or observation(observed_at=ANCHOR).observation.retailer_id,
    )
    vector = engineer().build([point], [inferred], as_of=inferred.start_date)
    assert vector is not None
    assert vector.categorical["sale_event_id"] is None
    assert vector.numeric["days_until_sale"] is None


def test_target_sale_price_is_not_copied_into_features() -> None:
    listing_id, variant_id = seed_ids()
    sale = event_record(
        start_date=ANCHOR + timedelta(days=20),
        end_date=ANCHOR + timedelta(days=26),
    )
    points = [
        observation(
            listing_id=listing_id,
            variant_id=variant_id,
            displayed_price="1000.00",
            effective_price="1000.00",
            observed_at=ANCHOR + timedelta(days=d),
        )
        for d in (1, 5, 10, 15)
    ]
    points.append(
        observation(
            listing_id=listing_id,
            variant_id=variant_id,
            displayed_price="432.10",
            effective_price="432.10",
            observed_at=sale.start_date + timedelta(days=1),
        )
    )
    examples = build_labeled_examples(points, [sale], engineer=engineer(), config=ml_config())
    assert len(examples) == 1
    example = examples[0]
    assert example.target_sale_price == Decimal("432.10")
    assert example.features.numeric["current_price"] != 432.10
    assert example.features.numeric["historical_low"] != 432.10
    assert example.features.as_of == sale.start_date
    preprocessor = FeaturePreprocessor().fit(examples)
    features, targets = preprocessor.transform(examples)
    assert matrix_contains_target(features, targets) is False
    assert not np.any(np.isclose(features, 432.10))
