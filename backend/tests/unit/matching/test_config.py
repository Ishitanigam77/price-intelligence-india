"""Matching configuration is environment-driven and has no hardcoded secrets."""

import pytest
from pydantic import ValidationError

from app.matching.config import MatchingConfig, get_matching_config


def test_defaults_use_hashing_backend_without_secrets() -> None:
    config = MatchingConfig(_env_file=None)
    assert config.embedding_backend == "hashing"
    assert "sentence-transformers/" in config.embedding_model
    assert config.title_high_threshold > config.title_medium_threshold
    assert config.embedding_high_threshold > config.embedding_medium_threshold
    secret_looking = [
        name
        for name in type(config).model_fields
        if name.endswith(("_secret", "_token", "_password", "_api_key"))
        or name in {"secret", "token", "password", "api_key"}
    ]
    assert secret_looking == []


def test_invalid_backend_is_rejected() -> None:
    with pytest.raises(ValidationError):
        MatchingConfig(_env_file=None, embedding_backend="scraping")


def test_blank_model_name_is_rejected() -> None:
    with pytest.raises(ValidationError):
        MatchingConfig(_env_file=None, embedding_model="  ")


def test_get_matching_config_cache_can_be_cleared(monkeypatch: pytest.MonkeyPatch) -> None:
    get_matching_config.cache_clear()
    monkeypatch.setenv("MATCHING_EMBEDDING_BACKEND", "hashing")
    monkeypatch.setenv("MATCHING_TITLE_HIGH_THRESHOLD", "0.91")
    get_matching_config.cache_clear()
    config = get_matching_config()
    assert config.embedding_backend == "hashing"
    assert config.title_high_threshold == 0.91
    get_matching_config.cache_clear()
