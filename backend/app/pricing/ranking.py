"""Deterministic, explainable ranking of retailer offers.

Order of keys (lowest/best first):

1. lowest verified effective price (available offers only)
2. lowest displayed price
3. availability
4. seller quality, where available
5. delivery information

Unavailable offers never win the verified-price ranking. Unverified promotional prices are
never used as the ranking price.
"""

from __future__ import annotations

from decimal import Decimal

from app.domain.enums import AvailabilityStatus
from app.pricing.enums import PriceKind, RankingCriterion
from app.pricing.models import ComparedOffer, RankingExplanation

_AVAILABILITY_RANK = {
    AvailabilityStatus.IN_STOCK: 0,
    AvailabilityStatus.LIMITED_STOCK: 1,
    AvailabilityStatus.UNKNOWN: 2,
    AvailabilityStatus.OUT_OF_STOCK: 3,
}

_MAX_MONEY = Decimal("999999999.99")


def _availability_rank(offer: ComparedOffer) -> int:
    return _AVAILABILITY_RANK.get(offer.availability, 2)


def _verified_rank_price(offer: ComparedOffer) -> tuple[int, Decimal]:
    """Group 0 = competes on verified price; group 1 = cannot."""
    if offer.can_win_verified_ranking and offer.effective_price is not None:
        return (0, offer.effective_price)
    return (1, _MAX_MONEY)


def _displayed_rank_price(offer: ComparedOffer) -> tuple[int, Decimal]:
    if offer.displayed_price is None:
        return (1, _MAX_MONEY)
    return (0, offer.displayed_price)


def _delivery_key(offer: ComparedOffer) -> tuple[int, Decimal]:
    if offer.delivery_fee is None:
        return (1, _MAX_MONEY)
    return (0, offer.delivery_fee)


def ranking_sort_key(offer: ComparedOffer) -> tuple:
    """Stable, fully deterministic sort key. Lower is better."""
    verified_group, verified_price = _verified_rank_price(offer)
    displayed_group, displayed_price = _displayed_rank_price(offer)
    return (
        verified_group,
        verified_price,
        displayed_group,
        displayed_price,
        _availability_rank(offer),
        -offer.seller.quality_score,
        *_delivery_key(offer),
        offer.retailer_slug,
        offer.offer_id,
    )


def rank_offers(offers: tuple[ComparedOffer, ...]) -> tuple[ComparedOffer, ...]:
    """Return offers sorted by the deterministic ranking keys, with 1-based `rank` assigned."""
    ordered = sorted(offers, key=ranking_sort_key)
    return tuple(
        offer.model_copy(update={"rank": index}) for index, offer in enumerate(ordered, start=1)
    )


def select_lowest_verified(
    ranked: tuple[ComparedOffer, ...],
) -> tuple[ComparedOffer | None, RankingExplanation]:
    """Pick the best available offer that has a verified ranking price, with an explanation."""
    eligible = [offer for offer in ranked if offer.can_win_verified_ranking]
    if not eligible:
        if not ranked:
            reason = "No retailer offers have been recorded for this variant."
        elif all(not offer.is_available for offer in ranked):
            reason = (
                "No available offers can win the verified-price ranking; "
                "every recorded offer is out of stock or otherwise unavailable."
            )
        else:
            reason = (
                "No offer has a verified price that can be ranked. "
                "Missing displayed prices prevent a verified comparison."
            )
        return None, RankingExplanation(
            criterion=RankingCriterion.NO_APPLICABLE_OFFER,
            reason=reason,
        )
    winner = eligible[0]
    runners_up = [offer for offer in eligible if offer.offer_id != winner.offer_id]
    criterion, tie_breakers, reason = _explain_selection(winner, tuple(runners_up))
    return winner, RankingExplanation(
        criterion=criterion,
        reason=reason,
        tie_breakers_applied=tie_breakers,
        selected_offer_id=winner.offer_id,
    )


def _format_money(value: Decimal | None, currency: str) -> str:
    if value is None:
        return "unavailable"
    return f"{currency} {value}"


def _explain_selection(
    winner: ComparedOffer, runners_up: tuple[ComparedOffer, ...]
) -> tuple[RankingCriterion, tuple[RankingCriterion, ...], str]:
    currency = winner.currency
    if not runners_up:
        if winner.price_kind is PriceKind.VERIFIED_EFFECTIVE:
            return (
                RankingCriterion.VERIFIED_EFFECTIVE_PRICE,
                (),
                (
                    f"Only available offer with a verified effective price of "
                    f"{_format_money(winner.effective_price, currency)}."
                ),
            )
        return (
            RankingCriterion.DISPLAYED_PRICE,
            (),
            (
                f"Only available offer; ranking fell back to displayed price "
                f"{_format_money(winner.displayed_price, currency)} "
                f"(no verified promotional adjustments applied)."
            ),
        )

    next_offer = runners_up[0]
    tie_breakers: list[RankingCriterion] = []

    if winner.effective_price != next_offer.effective_price:
        return (
            RankingCriterion.VERIFIED_EFFECTIVE_PRICE,
            (),
            (
                f"Lowest verified effective price "
                f"({_format_money(winner.effective_price, currency)} vs "
                f"{_format_money(next_offer.effective_price, currency)} on "
                f"{next_offer.retailer_slug}). Unverified promotional prices were not used."
            ),
        )
    tie_breakers.append(RankingCriterion.VERIFIED_EFFECTIVE_PRICE)

    if winner.displayed_price != next_offer.displayed_price:
        return (
            RankingCriterion.DISPLAYED_PRICE,
            tuple(tie_breakers),
            (
                f"Tied on verified effective price "
                f"({_format_money(winner.effective_price, currency)}); "
                f"selected for lowest displayed price "
                f"({_format_money(winner.displayed_price, currency)} vs "
                f"{_format_money(next_offer.displayed_price, currency)})."
            ),
        )
    tie_breakers.append(RankingCriterion.DISPLAYED_PRICE)

    if winner.availability is not next_offer.availability:
        return (
            RankingCriterion.AVAILABILITY,
            tuple(tie_breakers),
            (
                f"Tied on verified and displayed price; selected because availability is "
                f"{winner.availability.value} rather than {next_offer.availability.value}."
            ),
        )
    tie_breakers.append(RankingCriterion.AVAILABILITY)

    if winner.seller.quality_score != next_offer.seller.quality_score:
        return (
            RankingCriterion.SELLER_QUALITY,
            tuple(tie_breakers),
            (
                "Tied on price and availability; selected for higher seller quality "
                f"(first-party/active seller preferred; score {winner.seller.quality_score} vs "
                f"{next_offer.seller.quality_score})."
            ),
        )
    tie_breakers.append(RankingCriterion.SELLER_QUALITY)

    winner_delivery = "known" if winner.delivery_fee is not None else "missing"
    next_delivery = "known" if next_offer.delivery_fee is not None else "missing"
    if _delivery_key(winner) != _delivery_key(next_offer):
        return (
            RankingCriterion.DELIVERY,
            tuple(tie_breakers),
            (
                "Tied on price, availability, and seller quality; selected on delivery "
                f"information ({winner_delivery} delivery fee "
                f"{_format_money(winner.delivery_fee, currency)} vs {next_delivery} "
                f"{_format_money(next_offer.delivery_fee, currency)})."
            ),
        )
    return (
        RankingCriterion.DELIVERY,
        tuple(tie_breakers),
        (
            "Tied on every ranking key; selected by stable retailer/offer identity "
            f"({winner.retailer_slug}/{winner.offer_id})."
        ),
    )
