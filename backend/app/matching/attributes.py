"""Stage 2: normalized structured-attribute comparison.

Variant-defining attributes (RAM, storage, size, color, capacity, generation) that disagree
prevent `SAME_PRODUCT`. Missing attributes on one side are not conflicts. Accessory-vs-primary
listings are treated as different products.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from difflib import SequenceMatcher

from app.domain.exceptions import InvalidSlugError
from app.domain.validation import slugify
from app.matching.config import MatchingConfig
from app.matching.models import MatchCandidate

_KEY_ALIASES: dict[str, str] = {
    "colour": "color",
    "colors": "color",
    "colours": "color",
    "ram": "ram",
    "memory": "ram",
    "memory_size": "ram",
    "storage": "storage",
    "internal_storage": "storage",
    "rom": "storage",
    "ssd": "storage",
    "hdd": "storage",
    "size": "size",
    "screen_size": "size",
    "display_size": "size",
    "capacity": "capacity",
    "coverage": "capacity",
    "volume": "capacity",
    "tank": "capacity",
    "generation": "generation",
    "gen": "generation",
    "variant": "variant",
    "style": "variant",
    "model": "model",
    "model_number": "model",
    "model-number": "model",
    "brand": "brand",
}

VARIANT_KEYS = frozenset({"ram", "storage", "size", "color", "capacity", "generation", "variant"})
IDENTITY_KEYS = frozenset({"brand", "model"})

_SPEC_PATTERN = re.compile(
    r"(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>tb|gb|mb|ml|l|kg|g|inch|in|cm|mm|sqft|sq\s*ft)?",
    re.IGNORECASE,
)
_GENERATION_IN_TEXT = re.compile(
    r"\b(?:gen(?:eration)?\s*(?P<a>\d+)|(?P<b>\d+)(?:st|nd|rd|th)\s*gen(?:eration)?)\b",
    re.IGNORECASE,
)
_RAM_IN_TEXT = re.compile(r"\b(\d+(?:\.\d+)?)\s*gb\s*ram\b", re.IGNORECASE)
_STORAGE_IN_TEXT = re.compile(r"\b(\d+(?:\.\d+)?)\s*(tb|gb)\b(?!\s*ram)", re.IGNORECASE)

ACCESSORY_TOKENS = frozenset(
    {
        "case",
        "cover",
        "charger",
        "cable",
        "protector",
        "tempered",
        "glass",
        "pouch",
        "sleeve",
        "stand",
        "mount",
        "adapter",
        "skin",
        "film",
        "bumper",
        "holster",
        "strap",
        "screenprotector",
        "backcover",
    }
)
PRIMARY_TOKENS = frozenset(
    {
        "smartphone",
        "phone",
        "mobile",
        "laptop",
        "notebook",
        "earbuds",
        "earbud",
        "headphones",
        "headphone",
        "buds",
        "soundbar",
        "television",
        "tv",
        "purifier",
        "refrigerator",
        "washer",
        "camera",
        "tablet",
        "watch",
        "console",
    }
)
_MODEL_SKIP_TOKENS = ACCESSORY_TOKENS | {
    "gb",
    "tb",
    "ram",
    "ssd",
    "hdd",
    "5g",
    "4g",
    "lte",
    "wifi",
    "in",
    "ear",
    "inch",
    "wireless",
    "wired",
    "bluetooth",
    "smart",
    "edition",
    "series",
    "smartphone",
    "phone",
    "mobile",
    "laptop",
    "notebook",
    "headphones",
    "headphone",
    "television",
    "tv",
}
COLOR_WORDS = frozenset(
    {
        "black",
        "white",
        "silver",
        "gold",
        "blue",
        "red",
        "green",
        "grey",
        "gray",
        "midnight",
        "charcoal",
        "slate",
        "beige",
        "pink",
        "purple",
        "orange",
        "yellow",
        "bronze",
        "graphite",
        "starlight",
        "cream",
    }
)


def canonical_attribute_key(key: str) -> str:
    stripped = key.strip().lower().replace("-", "_").replace(" ", "_")
    return _KEY_ALIASES.get(stripped, stripped)


def canonical_attribute_value(key: str, value: str) -> str:
    raw = " ".join(str(value).strip().lower().split())
    raw = raw.replace("colour", "color")
    if key in {"ram", "storage", "capacity", "size"}:
        match = _SPEC_PATTERN.search(raw)
        if match:
            number = _trim_number(match.group("num"))
            unit = (match.group("unit") or "").lower().replace(" ", "")
            if unit == "in":
                unit = "inch"
            if unit == "sq ft":
                unit = "sqft"
            return f"{number}{unit}"
    if key == "generation":
        gen = _GENERATION_IN_TEXT.search(raw)
        if gen:
            return gen.group("a") or gen.group("b")
        digits = re.sub(r"\D", "", raw)
        return digits or raw
    return raw


def _trim_number(value: str) -> str:
    if "." in value:
        return str(float(value)).rstrip("0").rstrip(".") if "." in str(float(value)) else value
    return str(int(value)) if value.isdigit() else value


def normalize_attribute_map(attributes: Mapping[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for raw_key, raw_value in attributes.items():
        key = canonical_attribute_key(str(raw_key))
        value = canonical_attribute_value(key, str(raw_value))
        if key and value:
            normalized[key] = value
    return normalized


def extract_title_attributes(title: str) -> dict[str, str]:
    """Pull variant hints from a title so unstructured listings still separate variants."""
    found: dict[str, str] = {}
    ram = _RAM_IN_TEXT.search(title)
    if ram:
        found["ram"] = f"{_trim_number(ram.group(1))}gb"
    storage = None
    for match in _STORAGE_IN_TEXT.finditer(title):
        unit = match.group(2).lower()
        candidate = f"{_trim_number(match.group(1))}{unit}"
        if found.get("ram") != candidate:
            storage = candidate
    if storage:
        found["storage"] = storage
    gen = _GENERATION_IN_TEXT.search(title)
    if gen:
        found["generation"] = gen.group("a") or gen.group("b")
    colors = [word for word in _tokenize(title) if word in COLOR_WORDS]
    if colors:
        found["color"] = " ".join(colors)
    return found


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def brand_signature(candidate: MatchCandidate) -> str | None:
    if candidate.brand_slug:
        return candidate.brand_slug.strip().lower()
    if candidate.brand_name:
        try:
            return slugify(candidate.brand_name)
        except InvalidSlugError:
            return " ".join(candidate.brand_name.lower().split()) or None
    return None


def brands_match(left: MatchCandidate, right: MatchCandidate, *, ratio: float) -> bool | None:
    left_sig = brand_signature(left)
    right_sig = brand_signature(right)
    if not left_sig or not right_sig:
        return None
    if left_sig == right_sig:
        return True
    if left_sig in right_sig or right_sig in left_sig:
        return True
    return SequenceMatcher(None, left_sig, right_sig).ratio() >= ratio


def derive_model_hint(candidate: MatchCandidate, *, attributes: Mapping[str, str]) -> str | None:
    if attributes.get("model"):
        return canonical_attribute_value("model", attributes["model"])
    tokens = _tokenize(candidate.title)
    brand_tokens: set[str] = set()
    if candidate.brand_name:
        brand_tokens.update(_tokenize(candidate.brand_name))
    if candidate.brand_slug:
        brand_tokens.update(candidate.brand_slug.split("-"))
    skip = brand_tokens | _MODEL_SKIP_TOKENS | COLOR_WORDS
    kept: list[str] = []
    for token in tokens:
        if token in skip:
            continue
        if re.fullmatch(r"\d+(gb|tb|mb|mm|cm)", token):
            continue
        if token.isdigit() and int(token) >= 32:
            continue
        kept.append(token)
    if not kept:
        return None
    return " ".join(kept[:4])


def models_match(left_hint: str | None, right_hint: str | None, *, ratio: float) -> bool | None:
    if not left_hint or not right_hint:
        return None
    if left_hint == right_hint:
        return True
    if left_hint in right_hint or right_hint in left_hint:
        return True
    return SequenceMatcher(None, left_hint, right_hint).ratio() >= ratio


def colors_agree(left: str, right: str) -> bool:
    if left == right:
        return True
    left_parts = set(left.split())
    right_parts = set(right.split())
    if left_parts & right_parts:
        return True
    return left in right or right in left


def values_agree(key: str, left: str, right: str) -> bool:
    if key == "color":
        return colors_agree(left, right)
    return left == right


def is_accessory_listing(candidate: MatchCandidate, tokens: set[str]) -> bool:
    slug = (candidate.category_slug or "").lower()
    if "accessor" in slug:
        return True
    has_accessory = bool(tokens & ACCESSORY_TOKENS)
    has_primary = bool(tokens & PRIMARY_TOKENS)
    return has_accessory and not has_primary


def accessory_mismatch(left: MatchCandidate, right: MatchCandidate) -> bool:
    left_tokens = set(_tokenize(left.title))
    right_tokens = set(_tokenize(right.title))
    left_acc = is_accessory_listing(left, left_tokens)
    right_acc = is_accessory_listing(right, right_tokens)
    return left_acc != right_acc


def merge_attributes(candidate: MatchCandidate) -> dict[str, str]:
    merged = extract_title_attributes(candidate.title)
    merged.update(normalize_attribute_map(candidate.variant_attributes))
    return merged


def compare_attributes(
    left: MatchCandidate, right: MatchCandidate, config: MatchingConfig
) -> dict[str, object]:
    left_attrs = merge_attributes(left)
    right_attrs = merge_attributes(right)
    left_model = derive_model_hint(left, attributes=left_attrs)
    right_model = derive_model_hint(right, attributes=right_attrs)
    brand = brands_match(left, right, ratio=config.model_hint_ratio)
    model = models_match(left_model, right_model, ratio=config.model_hint_ratio)
    model_conflict = model is False

    overlapping_keys: list[str] = []
    agreements: list[str] = []
    conflicts: list[dict[str, str]] = []
    variant_conflicts: list[dict[str, str]] = []

    keys = sorted(set(left_attrs) | set(right_attrs))
    for key in keys:
        if key in IDENTITY_KEYS:
            continue
        left_value = left_attrs.get(key)
        right_value = right_attrs.get(key)
        if not left_value or not right_value:
            continue
        overlapping_keys.append(key)
        if values_agree(key, left_value, right_value):
            agreements.append(key)
        else:
            item = {"key": key, "left": left_value, "right": right_value}
            conflicts.append(item)
            if key in VARIANT_KEYS:
                variant_conflicts.append(item)

    return {
        "left_attributes": left_attrs,
        "right_attributes": right_attrs,
        "brand_match": brand,
        "model_match": model,
        "model_conflict": model_conflict,
        "left_model_hint": left_model,
        "right_model_hint": right_model,
        "overlapping_variant_keys": [key for key in overlapping_keys if key in VARIANT_KEYS],
        "agreements": agreements,
        "conflicts": conflicts,
        "variant_conflicts": variant_conflicts,
        "accessory_mismatch": accessory_mismatch(left, right),
    }
