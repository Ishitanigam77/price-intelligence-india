"""Collection config is environment-driven and fails closed on bad values."""

import pytest
from pydantic import ValidationError

from app.collectors.config import CollectionConfig, collection_config_from_settings
from app.core.config import Settings


def test_collection_config_from_settings() -> None:
    settings = Settings(
        _env_file=None,
        collection_max_retries=4,
        collection_operation_timeout_seconds=9.0,
        collection_default_search_query="fictional phone",
    )
    config = collection_config_from_settings(settings)
    assert config.max_retries == 4
    assert config.max_attempts == 5
    assert config.operation_timeout_seconds == 9.0
    assert config.default_search_query == "fictional phone"


def test_collection_config_rejects_unbounded_retries() -> None:
    with pytest.raises(ValidationError):
        CollectionConfig(max_retries=99)
