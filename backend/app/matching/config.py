"""Configurable matching thresholds, weights, and embedding backend selection.

Sourced from `MATCHING_*` environment variables. No secrets are required for local hashing
embeddings or for a locally cached Sentence Transformer model. If a private model hub token is
needed later, it must come from the environment / Key Vault — never from this module.
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class MatchingConfig(BaseSettings):
    """Environment-driven matching configuration, independent of FastAPI settings."""

    model_config = SettingsConfigDict(
        env_prefix="MATCHING_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    #: `hashing` is the default so tests and CI never download a model. Production should set
    #: `sentence_transformers` once the chosen model is available locally or from a permitted cache.
    embedding_backend: str = "hashing"
    #: Hugging Face / Sentence Transformer model id. Not a secret.
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = Field(default=256, ge=32, le=4096)
    embedding_cache_size: int = Field(default=2048, ge=0, le=100_000)

    title_high_threshold: float = Field(default=0.82, ge=0.0, le=1.0)
    title_medium_threshold: float = Field(default=0.60, ge=0.0, le=1.0)
    embedding_high_threshold: float = Field(default=0.86, ge=0.0, le=1.0)
    embedding_medium_threshold: float = Field(default=0.72, ge=0.0, le=1.0)
    fuzzy_token_ratio: float = Field(default=0.84, ge=0.0, le=1.0)
    model_hint_ratio: float = Field(default=0.86, ge=0.0, le=1.0)

    weight_identifier: float = Field(default=0.45, ge=0.0, le=1.0)
    weight_attributes: float = Field(default=0.35, ge=0.0, le=1.0)
    weight_title: float = Field(default=0.12, ge=0.0, le=1.0)
    weight_embedding: float = Field(default=0.08, ge=0.0, le=1.0)

    same_product_min_score: float = Field(default=0.78, ge=0.0, le=1.0)
    possible_match_min_score: float = Field(default=0.52, ge=0.0, le=1.0)
    needs_review_min_score: float = Field(default=0.34, ge=0.0, le=1.0)
    min_variant_agreements_for_same: int = Field(default=2, ge=1, le=10)

    @field_validator("embedding_backend")
    @classmethod
    def _validate_backend(cls, value: str) -> str:
        normalized = value.strip().lower()
        allowed = {"hashing", "sentence_transformers"}
        if normalized not in allowed:
            raise ValueError(f"embedding_backend must be one of {sorted(allowed)}, got {value!r}.")
        return normalized

    @field_validator("embedding_model")
    @classmethod
    def _validate_model_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("embedding_model must not be blank.")
        return stripped

    @property
    def stage_weights(self) -> dict[str, float]:
        return {
            "exact_identifiers": self.weight_identifier,
            "normalized_attributes": self.weight_attributes,
            "title_token_similarity": self.weight_title,
            "embedding_similarity": self.weight_embedding,
        }


@lru_cache
def get_matching_config() -> MatchingConfig:
    """Cached matching config. Tests that mutate env should call `cache_clear()`."""
    return MatchingConfig()
