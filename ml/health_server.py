"""Liveness and readiness HTTP server for the ML container.

This is an operations probe only. It does not serve predictions, train models, or expose
retailer data. Sale-price inference continues to live on the backend API
(`GET /api/v1/products/{id}/sale-price-prediction`).

Uses the Python standard library so the `ml` package does not import FastAPI.
Telemetry configuration is optional and must never prevent the probe from starting.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ml.config import get_ml_config


def _environment() -> str:
    return os.environ.get("ENVIRONMENT", "development")


def _artifact_ready() -> bool:
    config = get_ml_config()
    path = config.model_artifact_path.strip()
    if not path:
        return False
    return Path(path).exists()


def _health_payload() -> dict[str, str]:
    config = get_ml_config()
    artifact_configured = "true" if config.model_artifact_path.strip() else "false"
    return {
        "status": "ok",
        "service": "ml",
        "environment": _environment(),
        "artifact_path_configured": artifact_configured,
    }


def _readiness_payload() -> tuple[int, dict[str, object]]:
    config = get_ml_config()
    configured = bool(config.model_artifact_path.strip())
    present = _artifact_ready()
    # A missing artifact is expected before the first training run — the process is still
    # live. Readiness is ok when the process can serve probes; artifact state is reported
    # separately so operators can see INSUFFICIENT_DATA vs a crashed container.
    payload: dict[str, object] = {
        "status": "ok",
        "service": "ml",
        "environment": _environment(),
        "checks": {
            "process": {"status": "ok"},
            "model_artifact": {
                "status": "ok" if present else ("not_configured" if not configured else "unavailable")
            },
        },
    }
    return 200, payload


class HealthHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        # Inherited logger writes method/path/status only — no headers or bodies.
        super().log_message(format, *args)

    def _send_json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path in {"/health", "/health/", "/", "/health/live"}:
            try:
                self._send_json(200, _health_payload())
            except Exception:
                self._send_json(503, {"status": "unavailable", "service": "ml"})
            return
        if self.path in {"/health/ready", "/ready"}:
            try:
                code, payload = _readiness_payload()
                self._send_json(code, payload)
            except Exception:
                self._send_json(503, {"status": "unavailable", "service": "ml"})
            return
        self._send_json(404, {"status": "not_found", "service": "ml"})


def _configure_ml_telemetry() -> None:
    """Best-effort Application Insights wiring. Missing config must not block probes."""
    try:
        from app.observability.telemetry import configure_telemetry
    except Exception:
        return
    try:
        configure_telemetry(
            service_name="ml",
            environment=_environment(),
            connection_string=os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", ""),
        )
    except Exception:
        return


def main() -> None:
    _configure_ml_telemetry()
    port = int(os.environ.get("ML_HEALTH_PORT", "8080"))
    host = os.environ.get("ML_HEALTH_HOST", "0.0.0.0")
    server = ThreadingHTTPServer((host, port), HealthHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
