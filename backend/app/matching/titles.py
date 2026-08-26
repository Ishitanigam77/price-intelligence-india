"""Stage 3: normalized title / token similarity.

Handles punctuation, word order, common formatting, and mild spelling differences.
Title similarity is supporting evidence only — it must never be the sole reason for
`SAME_PRODUCT`.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from difflib import SequenceMatcher

from app.matching.config import MatchingConfig

_PUNCT_RE = re.compile(r"[^a-z0-9]+")
_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "for",
        "with",
        "in",
        "on",
        "to",
        "by",
        "from",
        "new",
        "latest",
        "original",
        "official",
        "genuine",
        "pack",
        "combo",
        "offer",
        "deal",
        "sale",
        "best",
        "price",
        "buy",
        "online",
        "store",
        "marketplace",
        "assured",
        "warranty",
        "edition",
        "version",
        "only",
        "launched",
    }
)
_SYNONYMS: dict[str, str] = {
    "colour": "color",
    "colours": "color",
    "smartphone": "phone",
    "smartphones": "phone",
    "mobile": "phone",
    "mobiles": "phone",
    "notebook": "laptop",
    "notebooks": "laptop",
    "earbuds": "buds",
    "earbud": "buds",
    "earphones": "buds",
    "headphone": "headphones",
    "tv": "television",
    "ssd": "storage",
    "hdd": "storage",
}


def normalize_title(title: str) -> str:
    lowered = title.strip().lower().replace("&", " and ")
    collapsed = _PUNCT_RE.sub(" ", lowered)
    return " ".join(collapsed.split())


def title_tokens(title: str) -> tuple[str, ...]:
    tokens: list[str] = []
    for raw in normalize_title(title).split():
        token = _SYNONYMS.get(raw, raw)
        if token in _STOPWORDS or not token:
            continue
        tokens.append(token)
    return tuple(tokens)


def _tokens_equivalent(left: str, right: str, *, ratio: float) -> bool:
    if left == right:
        return True
    if min(len(left), len(right)) < 4:
        return False
    return SequenceMatcher(None, left, right).ratio() >= ratio


def fuzzy_jaccard(left: tuple[str, ...], right: tuple[str, ...], *, ratio: float) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    remaining = list(right)
    matched = 0
    for token in left:
        found_index: int | None = None
        best_ratio = 0.0
        for index, candidate in enumerate(remaining):
            if token == candidate:
                found_index = index
                break
            similarity = SequenceMatcher(None, token, candidate).ratio()
            if similarity > best_ratio and _tokens_equivalent(token, candidate, ratio=ratio):
                best_ratio = similarity
                found_index = index
        if found_index is not None:
            matched += 1
            remaining.pop(found_index)
    union = len(left) + len(right) - matched
    return matched / union if union else 1.0


def token_sort_ratio(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    left_sorted = " ".join(sorted(left))
    right_sorted = " ".join(sorted(right))
    if not left_sorted and not right_sorted:
        return 1.0
    if not left_sorted or not right_sorted:
        return 0.0
    return SequenceMatcher(None, left_sorted, right_sorted).ratio()


def title_similarity(
    left_title: str, right_title: str, config: MatchingConfig
) -> dict[str, object]:
    left_tokens = title_tokens(left_title)
    right_tokens = title_tokens(right_title)
    jaccard = fuzzy_jaccard(left_tokens, right_tokens, ratio=config.fuzzy_token_ratio)
    sorted_ratio = token_sort_ratio(left_tokens, right_tokens)
    score = round(0.62 * jaccard + 0.38 * sorted_ratio, 4)
    return {
        "left_normalized": normalize_title(left_title),
        "right_normalized": normalize_title(right_title),
        "left_tokens": list(left_tokens),
        "right_tokens": list(right_tokens),
        "fuzzy_jaccard": round(jaccard, 4),
        "token_sort_ratio": round(sorted_ratio, 4),
        "score": score,
    }


def embedding_document(title: str, brand_name: str | None, attributes: Mapping[str, str]) -> str:
    """Stable text blob used by the embedding stage (brand + title + attributes)."""
    attr_text = " ".join(f"{key} {value}" for key, value in sorted(attributes.items()))
    return normalize_title(" ".join(part for part in (brand_name or "", title, attr_text) if part))
