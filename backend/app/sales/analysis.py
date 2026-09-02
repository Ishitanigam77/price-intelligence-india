"""Historical per-event, per-retailer sale statistics from stored observations.

All outputs are CALCULATED from OBSERVED snapshots overlapping persisted SaleEvent
windows. Future prices are not produced here.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
from decimal import Decimal
from statistics import median

from app.pricing.enums import MetricStatus
from app.pricing.history import qualifying_observations
from app.pricing.money import quantize_money, quantize_ratio
from app.sales.config import SalesConfig, get_sales_config
from app.sales.families import family_key
from app.sales.models import SaleEventRecord, SalePricePoint
from app.sales.timing_models import HistoricalSaleOccurrence


def _median_money(values: Sequence[Decimal]) -> Decimal | None:
    if not values:
        return None
    return quantize_money(Decimal(str(median(values))))


def analyze_occurrences(
    events: Sequence[SaleEventRecord],
    points: Sequence[SalePricePoint],
    *,
    config: SalesConfig | None = None,
) -> tuple[HistoricalSaleOccurrence, ...]:
    """One row per (event, retailer) that has in-window qualifying observations."""
    resolved = config if config is not None else get_sales_config()
    lookback = timedelta(days=resolved.pre_sale_lookback_days)
    qualifying = qualifying_observations(tuple(item.observation for item in points))
    rows: list[HistoricalSaleOccurrence] = []
    for event in events:
        retailers: dict[tuple, list] = {}
        scoped = event.retailer_id
        for point in qualifying:
            if not (event.start_date <= point.observed_at <= event.end_date):
                continue
            if scoped is not None and point.retailer_id != scoped:
                continue
            key = (point.retailer_id, point.retailer_slug, point.retailer_name)
            retailers.setdefault(key, []).append(point.analysis_price)
        for (retailer_id, slug, name), sale_prices in retailers.items():
            pre = [
                point.analysis_price
                for point in qualifying
                if point.retailer_id == retailer_id
                and event.start_date - lookback <= point.observed_at < event.start_date
            ]
            pre_sale = _median_money(pre)
            sale = _median_money(sale_prices)
            sale_min = quantize_money(min(sale_prices)) if sale_prices else None
            amount = None
            percent = None
            if pre_sale is not None and sale is not None and pre_sale > 0 and sale < pre_sale:
                amount = quantize_money(pre_sale - sale)
                percent = quantize_ratio(amount / pre_sale * Decimal("100"))
            duration = max(
                0, int(round((event.end_date - event.start_date).total_seconds() / 86400.0))
            )
            min_obs = resolved.min_observations_for_sale_stats
            usable = sale is not None and len(sale_prices) >= min_obs
            rows.append(
                HistoricalSaleOccurrence(
                    event_id=event.id,
                    sale_family=family_key(event),
                    retailer_id=retailer_id,
                    retailer_slug=slug,
                    retailer_name=name,
                    start_date=event.start_date,
                    end_date=event.end_date,
                    duration_days=duration,
                    observation_count=len(sale_prices),
                    pre_sale_price=pre_sale,
                    sale_price=sale,
                    minimum_sale_price=sale_min,
                    absolute_savings=amount,
                    percentage_savings=percent,
                    status=(
                        MetricStatus.AVAILABLE if usable else MetricStatus.INSUFFICIENT_HISTORY
                    ),
                )
            )
    rows.sort(key=lambda item: (item.start_date, str(item.retailer_id), item.event_id))
    return tuple(rows)
