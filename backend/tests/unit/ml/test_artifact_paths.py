"""Model version paths must stay inside the artifact root."""

from pathlib import Path

import pytest

from ml.inference.registry import load_model
from ml.models.artifact import InvalidModelVersionError, version_dir


def test_version_dir_rejects_path_traversal(tmp_path: Path) -> None:
    with pytest.raises(InvalidModelVersionError):
        version_dir(tmp_path, "../secret")
    with pytest.raises(InvalidModelVersionError):
        version_dir(tmp_path, "sale-price-xgb/../etc")
    with pytest.raises(InvalidModelVersionError):
        version_dir(tmp_path, "sale-price-xgb/features")


def test_version_dir_accepts_legitimate_versions(tmp_path: Path) -> None:
    directory = version_dir(tmp_path, "sale-price-xgb-features-v1-20260829T070100Z")
    assert directory.parent == tmp_path.resolve()


def test_load_model_returns_none_for_unsafe_version(tmp_path: Path) -> None:
    assert load_model(tmp_path, model_version="../etc/passwd") is None
