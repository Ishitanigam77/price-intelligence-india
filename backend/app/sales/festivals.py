"""Public Indian civil/festival calendar facts used only for festival-relative mapping.

These dates are calendar references, not retailer sale announcements and not predicted
prices. A sale is never marked CONFIRMED because it falls near a festival.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

# Fixed civil dates (same month-day every year).
FIXED_OCCASIONS: dict[str, tuple[int, int]] = {
    "new_year": (1, 1),
    "republic_day": (1, 26),
    "independence_day": (8, 15),
    "gandhi_jayanti": (10, 2),
    "christmas": (12, 25),
}

# Public festival dates (main civil/observance day) for years we may have history.
# Values are calendar facts published for those years; they are not sale windows.
_VARIABLE_FESTIVALS: dict[str, dict[int, date]] = {
    "diwali": {
        2020: date(2020, 11, 14),
        2021: date(2021, 11, 4),
        2022: date(2022, 10, 24),
        2023: date(2023, 11, 12),
        2024: date(2024, 10, 31),
        2025: date(2025, 10, 20),
        2026: date(2026, 11, 8),
        2027: date(2027, 10, 29),
        2028: date(2028, 10, 17),
    },
    "holi": {
        2020: date(2020, 3, 10),
        2021: date(2021, 3, 29),
        2022: date(2022, 3, 18),
        2023: date(2023, 3, 8),
        2024: date(2024, 3, 25),
        2025: date(2025, 3, 14),
        2026: date(2026, 3, 3),
        2027: date(2027, 3, 22),
        2028: date(2028, 3, 11),
    },
}


def occasion_date(occasion_id: str, year: int) -> date | None:
    """Return the calendar date of `occasion_id` in `year`, or None if unknown."""
    if occasion_id in FIXED_OCCASIONS:
        month, day = FIXED_OCCASIONS[occasion_id]
        try:
            return date(year, month, day)
        except ValueError:
            return None
    table = _VARIABLE_FESTIVALS.get(occasion_id)
    if table is None:
        return None
    return table.get(year)


def all_occasion_ids() -> tuple[str, ...]:
    return tuple(FIXED_OCCASIONS) + tuple(_VARIABLE_FESTIVALS)


def aware_midnight(value: date) -> datetime:
    return datetime(value.year, value.month, value.day, tzinfo=UTC)


def offset_days(event_start: datetime, occasion: date) -> int:
    start_date = event_start.astimezone(UTC).date()
    return (start_date - occasion).days


def apply_offset(occasion: date, days: int, *, duration_days: int) -> tuple[datetime, datetime]:
    start = occasion + timedelta(days=days)
    end = start + timedelta(days=max(0, duration_days))
    return aware_midnight(start), datetime(end.year, end.month, end.day, 23, 59, 59, tzinfo=UTC)
