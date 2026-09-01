"""Phase 19 sale-timing intelligence: calendar + retailer outlook + major vs ordinary.

Reuses PriceComparisonEngine results, SaleEvent records, historical observations, and
optional Phase 10 predictions passed in as labeled PREDICTED inputs. Does not train a
model, does not scrape, and does not invent dates or prices.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from statistics import median

from app.domain.enums import (
    AvailabilityStatus,
    ConfidenceLevel,
    SaleEvidenceStatus,
    SaleSeverity,
)
from app.observability.logging import get_logger
from app.pricing.enums import MetricStatus, ValueKind
from app.pricing.models import ComparedOffer, VariantComparison
from app.pricing.money import quantize_money, quantize_ratio
from app.sales.analysis import analyze_occurrences
from app.sales.calendar import map_sale_calendar
from app.sales.config import SalesConfig, get_sales_config
from app.sales.models import SaleEventRecord, SalePricePoint
from app.sales.timing_models import (
    TIMING_DISCLAIMER,
    ExpectedSaleWindow,
    HistoricalSaleOccurrence,
    ListingPredictionInput,
    ProductSaleIntelligence,
    RetailerSaleOutlook,
    SaleOpportunity,
    VariantSaleIntelligence,
)

logger = get_logger(__name__)

_SECONDS_PER_DAY = 86400.0
_MIN_PREDICTION_CONFIDENCE = 0.50


def expected_savings(
    current: Decimal | None,
    future: Decimal | None,
) -> tuple[Decimal | None, Decimal | None]:
    """CALCULATED saving of current minus future. Never negative or invented."""
    if current is None or future is None or current <= 0:
        return None, None
    if future >= current:
        return None, None
    amount = quantize_money(current - future)
    percent = quantize_ratio(amount / current * Decimal("100"))
    return amount, percent


def _days_until(start: datetime | None, *, as_of: datetime) -> int | None:
    if start is None:
        return None
    seconds = (start - as_of).total_seconds()
    if seconds <= 0:
        return 0
    return int(seconds // _SECONDS_PER_DAY)


def _reliability(count: int) -> ConfidenceLevel | None:
    if count >= 3:
        return ConfidenceLevel.HIGH
    if count == 2:
        return ConfidenceLevel.MEDIUM
    if count == 1:
        return ConfidenceLevel.LOW
    return None


def _prediction_for(
    predictions: Sequence[ListingPredictionInput],
    retailer_id: uuid.UUID,
) -> ListingPredictionInput | None:
    usable = [
        item
        for item in predictions
        if item.retailer_id == retailer_id
        and item.status == "PREDICTED"
        and item.predicted_price is not None
        and item.confidence is not None
        and item.confidence >= _MIN_PREDICTION_CONFIDENCE
    ]
    if not usable:
        return None
    return max(usable, key=lambda item: item.confidence or 0.0)


def _historical_median(
    occurrences: Sequence[HistoricalSaleOccurrence],
    *,
    family: str,
    retailer_id: uuid.UUID,
) -> tuple[Decimal | None, int]:
    prices = [
        item.sale_price
        for item in occurrences
        if item.sale_family == family
        and item.retailer_id == retailer_id
        and item.status is MetricStatus.AVAILABLE
        and item.sale_price is not None
    ]
    if not prices:
        return None, 0
    return quantize_money(Decimal(str(median(prices)))), len(prices)


def _outlook(
    offer: ComparedOffer,
    *,
    window: ExpectedSaleWindow,
    occurrences: Sequence[HistoricalSaleOccurrence],
    predictions: Sequence[ListingPredictionInput],
    is_cheapest: bool,
) -> RetailerSaleOutlook:
    current = offer.effective_price if offer.effective_price is not None else offer.displayed_price
    current_kind = None
    if offer.effective_price is not None:
        current_kind = ValueKind.CALCULATED
    elif offer.displayed_price is not None:
        current_kind = ValueKind.OBSERVED
    predicted = _prediction_for(predictions, offer.retailer_id)
    historical, hist_count = _historical_median(
        occurrences, family=window.sale_family, retailer_id=offer.retailer_id
    )
    expected: Decimal | None = None
    expected_kind: ValueKind | None = None
    if predicted is not None and predicted.predicted_price is not None:
        expected = predicted.predicted_price
        expected_kind = ValueKind.PREDICTED
    elif historical is not None:
        expected = historical
        expected_kind = ValueKind.CALCULATED
    amount, percent = expected_savings(current, expected)
    if expected is None:
        return RetailerSaleOutlook(
            retailer_id=offer.retailer_id,
            retailer_slug=offer.retailer_slug,
            retailer_name=offer.retailer_name,
            current_price=current,
            current_price_value_kind=current_kind,
            availability=offer.availability,
            is_current_cheapest=is_cheapest,
            predicted_sale_price=predicted.predicted_price if predicted else None,
            predicted_lower_bound=predicted.lower_bound if predicted else None,
            predicted_upper_bound=predicted.upper_bound if predicted else None,
            predicted_confidence=predicted.confidence if predicted else None,
            historical_sale_price=historical,
            historical_occurrence_count=hist_count,
            reliability=_reliability(hist_count),
            status=MetricStatus.INSUFFICIENT_HISTORY,
            insufficient_reason=(
                "No usable predicted or historical sale price for this retailer and sale family."
            ),
        )
    conf = window.confidence
    if predicted is not None and predicted.confidence is not None and predicted.confidence < 0.65:
        conf = ConfidenceLevel.MEDIUM if conf is ConfidenceLevel.HIGH else conf
    if hist_count == 0 and expected_kind is ValueKind.PREDICTED:
        reliability = None
    else:
        reliability = _reliability(hist_count)
    return RetailerSaleOutlook(
        retailer_id=offer.retailer_id,
        retailer_slug=offer.retailer_slug,
        retailer_name=offer.retailer_name,
        current_price=current,
        current_price_value_kind=current_kind,
        availability=offer.availability,
        is_current_cheapest=is_cheapest,
        expected_sale_price=expected,
        expected_sale_price_value_kind=expected_kind,
        predicted_sale_price=predicted.predicted_price if predicted else None,
        predicted_lower_bound=predicted.lower_bound if predicted else None,
        predicted_upper_bound=predicted.upper_bound if predicted else None,
        predicted_confidence=predicted.confidence if predicted else None,
        historical_sale_price=historical,
        historical_occurrence_count=hist_count,
        expected_saving=amount,
        expected_saving_percentage=percent,
        expected_saving_value_kind=ValueKind.CALCULATED if amount is not None else None,
        confidence=conf,
        reliability=reliability,
        status=MetricStatus.AVAILABLE,
    )


def _best_expected(
    outlooks: Sequence[RetailerSaleOutlook],
) -> RetailerSaleOutlook | None:
    usable = [
        item
        for item in outlooks
        if item.status is MetricStatus.AVAILABLE
        and item.expected_sale_price is not None
        and item.availability is not AvailabilityStatus.OUT_OF_STOCK
    ]
    if not usable:
        return None
    return min(
        usable,
        key=lambda item: (item.expected_sale_price, item.retailer_slug),
    )


def _opportunity(
    window: ExpectedSaleWindow,
    *,
    offers: Sequence[ComparedOffer],
    cheapest_id: uuid.UUID | None,
    occurrences: Sequence[HistoricalSaleOccurrence],
    predictions: Sequence[ListingPredictionInput],
    as_of: datetime,
) -> SaleOpportunity:
    if (
        window.evidence_status is SaleEvidenceStatus.UNKNOWN
        or window.expected_start_date is None
        or window.expected_end_date is None
    ):
        return SaleOpportunity(
            sale_type=window.sale_type,
            window=window,
            days_until_start=_days_until(window.expected_start_date, as_of=as_of),
            retailer_outlooks=(),
            status=MetricStatus.INSUFFICIENT_HISTORY,
            insufficient_reason=window.reason,
        )
    outlooks = tuple(
        _outlook(
            offer,
            window=window,
            occurrences=occurrences,
            predictions=predictions,
            is_cheapest=cheapest_id is not None and offer.retailer_id == cheapest_id,
        )
        for offer in offers
    )
    best = _best_expected(outlooks)
    days = _days_until(window.expected_start_date, as_of=as_of)
    if best is None:
        return SaleOpportunity(
            sale_type=window.sale_type,
            window=window,
            days_until_start=days,
            retailer_outlooks=outlooks,
            confidence=window.confidence,
            status=MetricStatus.INSUFFICIENT_HISTORY,
            insufficient_reason=("No retailer has a usable expected sale price for this window."),
        )
    return SaleOpportunity(
        sale_type=window.sale_type,
        window=window,
        expected_price=best.expected_sale_price,
        expected_price_value_kind=best.expected_sale_price_value_kind,
        expected_saving=best.expected_saving,
        expected_saving_percentage=best.expected_saving_percentage,
        expected_saving_value_kind=best.expected_saving_value_kind,
        days_until_start=days,
        likely_best_retailer_id=best.retailer_id,
        likely_best_retailer_slug=best.retailer_slug,
        likely_best_retailer_name=best.retailer_name,
        retailer_outlooks=outlooks,
        confidence=best.confidence,
        historical_reliability=best.reliability,
        status=MetricStatus.AVAILABLE,
    )


def _pick_window(
    windows: Sequence[ExpectedSaleWindow],
    severity: SaleSeverity,
    *,
    as_of: datetime,
) -> ExpectedSaleWindow | None:
    dated = [
        window
        for window in windows
        if window.sale_type is severity
        and window.expected_start_date is not None
        and window.expected_end_date is not None
        and window.evidence_status is not SaleEvidenceStatus.UNKNOWN
        and window.expected_end_date >= as_of
    ]
    if not dated:
        return None
    return min(dated, key=lambda item: (item.expected_start_date, item.sale_family))


class SaleIntelligenceEngine:
    """Composes calendar mapping, historical sale stats, and optional predictions."""

    def __init__(self, config: SalesConfig | None = None) -> None:
        self._config = config if config is not None else get_sales_config()

    def compute_variant(
        self,
        *,
        product_id: uuid.UUID,
        product_variant_id: uuid.UUID,
        variant_key: str | None,
        comparison: VariantComparison | None,
        events: Sequence[SaleEventRecord],
        points: Sequence[SalePricePoint],
        predictions: Sequence[ListingPredictionInput] = (),
        as_of: datetime,
    ) -> VariantSaleIntelligence:
        occurrences = analyze_occurrences(events, points, config=self._config)
        calendar = map_sale_calendar(events, points, as_of=as_of, config=self._config)
        offers = comparison.offers if comparison is not None else ()
        cheapest = comparison.lowest_verified_offer if comparison is not None else None
        cheapest_id = cheapest.retailer_id if cheapest is not None else None
        ordinary_window = _pick_window(calendar, SaleSeverity.ORDINARY, as_of=as_of)
        major_window = _pick_window(calendar, SaleSeverity.MAJOR, as_of=as_of)
        ordinary = (
            _opportunity(
                ordinary_window,
                offers=offers,
                cheapest_id=cheapest_id,
                occurrences=occurrences,
                predictions=predictions,
                as_of=as_of,
            )
            if ordinary_window is not None
            else None
        )
        major = (
            _opportunity(
                major_window,
                offers=offers,
                cheapest_id=cheapest_id,
                occurrences=occurrences,
                predictions=predictions,
                as_of=as_of,
            )
            if major_window is not None
            else None
        )
        expected_best = None
        for candidate in (major, ordinary):
            if candidate is not None and candidate.status is MetricStatus.AVAILABLE:
                expected_best = _best_expected(candidate.retailer_outlooks)
                if expected_best is not None:
                    break
        current_price = None
        current_effective = None
        availability = None
        if cheapest is not None:
            current_effective = cheapest.effective_price
            current_price = (
                cheapest.effective_price
                if cheapest.effective_price is not None
                else cheapest.displayed_price
            )
            availability = cheapest.availability
        logger.info(
            "sales.intelligence.variant_computed",
            extra={
                "product_id": str(product_id),
                "product_variant_id": str(product_variant_id),
                "calendar_windows": len(calendar),
                "has_ordinary": ordinary is not None,
                "has_major": major is not None,
            },
        )
        return VariantSaleIntelligence(
            product_id=product_id,
            product_variant_id=product_variant_id,
            variant_key=variant_key,
            current_cheapest_retailer_id=cheapest_id,
            current_cheapest_retailer_slug=cheapest.retailer_slug if cheapest else None,
            current_cheapest_retailer_name=cheapest.retailer_name if cheapest else None,
            current_cheapest_price=current_price,
            current_effective_price=current_effective,
            current_availability=availability,
            occurrences=occurrences,
            calendar=calendar,
            ordinary=ordinary,
            major=major,
            expected_best_retailer=expected_best,
            disclaimer=TIMING_DISCLAIMER,
            calculated_at=as_of,
            predicted=None,
        )

    def compute_product(
        self,
        *,
        product_id: uuid.UUID,
        variant_comparisons: dict[uuid.UUID, VariantComparison],
        points_by_variant: dict[uuid.UUID, Sequence[SalePricePoint]],
        events: Sequence[SaleEventRecord],
        predictions_by_variant: dict[uuid.UUID, Sequence[ListingPredictionInput]] | None = None,
        variant_keys: dict[uuid.UUID, str | None] | None = None,
        as_of: datetime,
    ) -> ProductSaleIntelligence:
        pred_map = predictions_by_variant or {}
        keys = variant_keys or {}
        variant_ids = list(dict.fromkeys([*variant_comparisons.keys(), *points_by_variant.keys()]))
        variants = tuple(
            self.compute_variant(
                product_id=product_id,
                product_variant_id=variant_id,
                variant_key=keys.get(variant_id),
                comparison=variant_comparisons.get(variant_id),
                events=events,
                points=points_by_variant.get(variant_id, ()),
                predictions=pred_map.get(variant_id, ()),
                as_of=as_of,
            )
            for variant_id in variant_ids
        )
        return ProductSaleIntelligence(
            product_id=product_id,
            as_of=as_of,
            disclaimer=TIMING_DISCLAIMER,
            variants=variants,
            predicted=None,
        )
