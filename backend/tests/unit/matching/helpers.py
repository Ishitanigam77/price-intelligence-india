"""Shared builders for matching unit tests. All product data is fictional fixture data."""

from __future__ import annotations

from collections.abc import Mapping

from app.matching import (
    MatchCandidate,
    MatchIdentifier,
    MatchIdentifierType,
    MatchingConfig,
    MatchingEngine,
)
from app.matching.embeddings import HashingNgramEmbeddingProvider


def make_config(**overrides: object) -> MatchingConfig:
    return MatchingConfig(_env_file=None, **overrides)  # type: ignore[arg-type]


def make_engine(**overrides: object) -> MatchingEngine:
    config = make_config(**overrides)
    return MatchingEngine(
        config,
        embedding_provider=HashingNgramEmbeddingProvider(
            dimension=config.embedding_dimension, cache_size=config.embedding_cache_size
        ),
    )


def ident(identifier_type: MatchIdentifierType | str, value: str) -> MatchIdentifier:
    typed = (
        identifier_type
        if isinstance(identifier_type, MatchIdentifierType)
        else MatchIdentifierType(identifier_type)
    )
    return MatchIdentifier(identifier_type=typed, value=value)


def candidate(
    *,
    title: str,
    retailer_id: str = "mock-retailer-a",
    retailer_sku: str = "sku-1",
    source_url: str | None = "https://mock-retailer-a.example.test/p/sku-1",
    brand_name: str | None = "Fictional Orchard",
    brand_slug: str | None = "fictional-orchard",
    category_slug: str | None = "mobiles",
    identifiers: tuple[MatchIdentifier, ...] = (),
    variant_attributes: Mapping[str, str] | None = None,
) -> MatchCandidate:
    return MatchCandidate(
        retailer_id=retailer_id,
        retailer_sku=retailer_sku,
        source_url=source_url,
        title=title,
        brand_name=brand_name,
        brand_slug=brand_slug,
        category_slug=category_slug,
        identifiers=identifiers,
        variant_attributes=dict(variant_attributes or {}),
    )
