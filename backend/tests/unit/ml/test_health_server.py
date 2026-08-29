"""Health payload for the ML container liveness server."""

from ml.health_server import _health_payload


def test_ml_health_payload_is_ok_without_artifact_path() -> None:
    payload = _health_payload()
    assert payload["status"] == "ok"
    assert payload["service"] == "ml"
    assert payload["artifact_path_configured"] in {"true", "false"}
