"""Helpers for non-negative INR amounts used by the comparison engine."""

from decimal import ROUND_HALF_UP, Decimal

from app.domain.exceptions import NegativeAmountError
from app.domain.validation import validate_non_negative_amount

MONEY_QUANTUM = Decimal("0.01")
RATIO_QUANTUM = Decimal("0.0001")


def quantize_money(value: Decimal) -> Decimal:
    """Round a monetary amount to 2 decimal places (paise)."""
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def quantize_ratio(value: Decimal) -> Decimal:
    """Round a unitless ratio or percent to 4 decimal places."""
    return value.quantize(RATIO_QUANTUM, rounding=ROUND_HALF_UP)


def optional_money(value: Decimal | None, *, field_name: str) -> Decimal | None:
    """Validate and quantize an optional non-negative amount."""
    validated = validate_non_negative_amount(value, field_name=field_name)
    if validated is None:
        return None
    return quantize_money(validated)


def require_money(value: Decimal | None, *, field_name: str) -> Decimal:
    """Validate and quantize a required non-negative amount."""
    if value is None:
        raise NegativeAmountError(f"{field_name} is required and must not be None.")
    validated = validate_non_negative_amount(value, field_name=field_name)
    if validated is None:
        raise NegativeAmountError(f"{field_name} is required and must not be None.")
    return quantize_money(validated)
