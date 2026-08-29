"""Build labeled training rows from stored observations and sale events.

Each row predicts the observed effective sale price during a sale window from features
computed at the window's start. Rows are not invented: a listing without a pre-sale
observation or without in-window qualifying prices is skipped, not imputed.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from statistics import median

from app.pricing.history import qualifying_observations
from app.sales.applicability import applicable_events, observations_during_event
from app.sales.models import SaleEventRecord, SalePricePoint
from ml.config import MLConfig, get_ml_config
from ml.features.availability import observations_available_at
from ml.features.engineering import FeatureEngineer, listing_group_key
from ml.types import LabeledExample


def _listing_key_strings(point: SalePricePoint) -> tuple[str, str]:
    obs = point.observation
    seller = str(obs.seller_id) if obs.seller_id is not None else "none"
    return (str(obs.retailer_product_id), seller)


def build_labeled_examples(
    points: Sequence[SalePricePoint],
    events: Sequence[SaleEventRecord],
    *,
    engineer: FeatureEngineer | None = None,
    config: MLConfig | None = None,
) -> tuple[LabeledExample, ...]:
    """Construct leakage-safe supervised examples. Never fabricates prices or events."""
    cfg = config if config is not None else get_ml_config()
    feature_engineer = engineer if engineer is not None else FeatureEngineer()
    grouped: dict[tuple, list[SalePricePoint]] = defaultdict(list)
    for point in points:
        grouped[listing_group_key(point)].append(point)

    examples: list[LabeledExample] = []
    for group in grouped.values():
        first = group[0]
        obs = first.observation
        applicable = applicable_events(
            events,
            brand_id=first.brand_id,
            category_id=first.category_id,
            retailer_id=obs.retailer_id,
        )
        for event in applicable:
            during = observations_during_event(event, group)
            qualifying_during = qualifying_observations(during)
            if len(qualifying_during) < cfg.min_target_observations:
                continue
            as_of = event.start_date
            if not observations_available_at(
                tuple(item.observation for item in group), as_of=as_of
            ):
                continue
            features = feature_engineer.build(group, events, as_of=as_of, target_event=event)
            if features is None:
                continue
            prices = [point.analysis_price for point in qualifying_during]
            target = median(prices)
            examples.append(
                LabeledExample(
                    features=features,
                    target_sale_price=target,
                    target_event_id=event.id,
                    target_observation_count=len(qualifying_during),
                    listing_key=_listing_key_strings(first),
                )
            )
    examples.sort(key=lambda item: (item.features.as_of, item.target_event_id, item.listing_key))
    return tuple(examples)
