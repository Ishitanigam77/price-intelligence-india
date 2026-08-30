"""Health payload for the ML container liveness server."""

from ml.health_server import _health_payload, _readiness_payload


def test_ml_health_payload_is_ok_without_artifact_path() -> None:
    payload = _health_payload()
    assert payload["status"] == "ok"
    assert payload["service"] == "ml"
    assert payload["artifact_path_configured"] in {"true", "false"}
    assert "environment" in payload


def test_ml_readiness_payload_reports_artifact_without_failing() -> None:
    code, payload = _readiness_payload()
    assert code == 200
    assert payload["status"] == "ok"
    assert payload["service"] == "ml"
    assert "model_artifact" in payload["checks"]  # type: ignore[index]
