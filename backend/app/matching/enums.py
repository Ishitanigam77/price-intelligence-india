"""Classifications and method labels produced by the product matching engine.

These live in the matching package (not `app.domain`) so price-observation confidence and
match confidence cannot be conflated. Matching never imports FastAPI or a retailer adapter
package.
"""

from enum import StrEnum


class MatchClassification(StrEnum):
    """Whether two listings refer to the same sellable product variant."""

    SAME_PRODUCT = "SAME_PRODUCT"
    POSSIBLE_MATCH = "POSSIBLE_MATCH"
    DIFFERENT_PRODUCT = "DIFFERENT_PRODUCT"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class MatchMethod(StrEnum):
    """Which stage (or combination) produced the classification.

    Title similarity and embeddings are never recorded as the sole method for `SAME_PRODUCT`.
    """

    EXACT_IDENTIFIER = "exact_identifier"
    NORMALIZED_ATTRIBUTES = "normalized_attributes"
    TITLE_TOKEN_SIMILARITY = "title_token_similarity"
    EMBEDDING_SIMILARITY = "embedding_similarity"
    COMBINED = "combined"
    CONFLICTING_EVIDENCE = "conflicting_evidence"


class MatchConfidence(StrEnum):
    """Confidence in the classification, independent of price-observation confidence."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MatchIdentifierType(StrEnum):
    """Identifier kinds the matching engine compares.

    Mirrors Phase 1 `ProductIdentifierType` and adds `MODEL_NUMBER`, which is a matching-layer
    identity key (often carried as a variant attribute rather than a persisted identifier).
    """

    GTIN = "gtin"
    EAN = "ean"
    UPC = "upc"
    ISBN = "isbn"
    MPN = "mpn"
    MODEL_NUMBER = "model_number"
    OTHER = "other"


class IdentifierFamily(StrEnum):
    """Families inside which two typed values may be compared as the same identity."""

    BARCODE = "barcode"
    ISBN = "isbn"
    PART = "part"
    OTHER = "other"


class MatchStageName(StrEnum):
    """Stable names for the four pipeline stages."""

    EXACT_IDENTIFIERS = "exact_identifiers"
    NORMALIZED_ATTRIBUTES = "normalized_attributes"
    TITLE_TOKEN_SIMILARITY = "title_token_similarity"
    EMBEDDING_SIMILARITY = "embedding_similarity"
