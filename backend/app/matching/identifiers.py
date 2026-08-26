"""Stage 1: exact identifier comparison after format normalization.

Missing identifiers are never treated as a match. Values are compared only inside a family
(barcode, ISBN, manufacturer part / model number). Cross-family disagreement is not a conflict.
"""

from __future__ import annotations

import re

from app.matching.enums import IdentifierFamily, MatchIdentifierType
from app.matching.models import MatchCandidate, MatchIdentifier

_NON_ALNUM = re.compile(r"[^A-Z0-9]+")
_NON_DIGIT = re.compile(r"\D")
_ISBN10_TAIL = re.compile(r"^[0-9]{9}[0-9X]$")

_BARCODE_TYPES = frozenset(
    {
        MatchIdentifierType.GTIN,
        MatchIdentifierType.EAN,
        MatchIdentifierType.UPC,
    }
)
_PART_TYPES = frozenset({MatchIdentifierType.MPN, MatchIdentifierType.MODEL_NUMBER})

_FAMILY_BY_TYPE: dict[MatchIdentifierType, IdentifierFamily] = {
    MatchIdentifierType.GTIN: IdentifierFamily.BARCODE,
    MatchIdentifierType.EAN: IdentifierFamily.BARCODE,
    MatchIdentifierType.UPC: IdentifierFamily.BARCODE,
    MatchIdentifierType.ISBN: IdentifierFamily.ISBN,
    MatchIdentifierType.MPN: IdentifierFamily.PART,
    MatchIdentifierType.MODEL_NUMBER: IdentifierFamily.PART,
    MatchIdentifierType.OTHER: IdentifierFamily.OTHER,
}


def identifier_family(identifier_type: MatchIdentifierType) -> IdentifierFamily:
    return _FAMILY_BY_TYPE[identifier_type]


def normalize_barcode(value: str) -> str | None:
    """Return digits only, padded to GTIN-14 when the length is a known GTIN size.

    Returns `None` when no digits remain — callers must treat that as missing, not equal.
    """
    digits = _NON_DIGIT.sub("", value)
    if not digits:
        return None
    if len(digits) in {8, 12, 13, 14}:
        return digits.zfill(14)
    return digits


def isbn10_to_isbn13(isbn10: str) -> str | None:
    """Convert a compact ISBN-10 (9 digits + check, `X` allowed) to ISBN-13 digits."""
    compact = isbn10.upper()
    if not _ISBN10_TAIL.match(compact):
        return None
    body = f"978{compact[:9]}"
    total = sum(int(ch) * (1 if index % 2 == 0 else 3) for index, ch in enumerate(body))
    check = (10 - (total % 10)) % 10
    return f"{body}{check}"


def normalize_isbn(value: str) -> str | None:
    compact = _NON_ALNUM.sub("", value.upper())
    if not compact:
        return None
    if len(compact) == 13 and compact.isdigit():
        return compact
    if len(compact) == 10:
        converted = isbn10_to_isbn13(compact)
        return converted
    digits = _NON_DIGIT.sub("", compact)
    return digits or None


def normalize_part(value: str) -> str | None:
    compact = _NON_ALNUM.sub("", value.upper())
    return compact or None


def normalize_identifier(identifier: MatchIdentifier) -> str | None:
    family = identifier_family(identifier.identifier_type)
    if family is IdentifierFamily.BARCODE:
        return normalize_barcode(identifier.value)
    if family is IdentifierFamily.ISBN:
        return normalize_isbn(identifier.value)
    if family is IdentifierFamily.PART:
        return normalize_part(identifier.value)
    compact = identifier.value.strip().upper()
    return compact or None


def normalized_values_by_family(
    identifiers: tuple[MatchIdentifier, ...],
) -> dict[IdentifierFamily, set[str]]:
    grouped: dict[IdentifierFamily, set[str]] = {}
    for identifier in identifiers:
        normalized = normalize_identifier(identifier)
        if normalized is None:
            continue
        family = identifier_family(identifier.identifier_type)
        grouped.setdefault(family, set()).add(normalized)
        # ISBN-13 is a GTIN; a GTIN on the other side with the same digits is the same identity.
        if family is IdentifierFamily.ISBN and len(normalized) == 13:
            barcode = normalize_barcode(normalized)
            if barcode is not None:
                grouped.setdefault(IdentifierFamily.BARCODE, set()).add(barcode)
    return grouped


def compare_identifiers(left: MatchCandidate, right: MatchCandidate) -> dict[str, object]:
    """Compare normalized identifier families.

    `matches` and `conflicts` are disjoint. A family present on only one side is listed under
    `unilateral` and is neither a match nor a conflict.
    """
    left_groups = normalized_values_by_family(left.identifiers)
    right_groups = normalized_values_by_family(right.identifiers)
    families = set(left_groups) | set(right_groups)
    matches: list[dict[str, object]] = []
    conflicts: list[dict[str, object]] = []
    unilateral: list[str] = []
    for family in sorted(families, key=lambda item: item.value):
        left_values = left_groups.get(family, set())
        right_values = right_groups.get(family, set())
        if not left_values or not right_values:
            unilateral.append(family.value)
            continue
        shared = left_values & right_values
        if shared:
            matches.append(
                {
                    "family": family.value,
                    "values": sorted(shared),
                }
            )
            continue
        conflicts.append(
            {
                "family": family.value,
                "left": sorted(left_values),
                "right": sorted(right_values),
            }
        )
    return {
        "matches": matches,
        "conflicts": conflicts,
        "unilateral": unilateral,
        "left_families": sorted(family.value for family in left_groups),
        "right_families": sorted(family.value for family in right_groups),
    }
