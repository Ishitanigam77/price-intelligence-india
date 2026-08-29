"""Liveness HTTP server for the ML container.

This is an operations probe only. It does not serve predictions, train models, or expose
retailer data. Sale-price inference continues to live on the backend API
(`GET /api/v1/products/{id}/sale-price-prediction`).

Uses the Python standard library so the `ml` package does not import FastAPI.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ml.config import get_ml_config


def _health_payload() -> dict[str, str]:
    config = get_ml_config()
    artifact_configured = "true" if config.model_artifact_path.strip() else "false"
    return {
        "status": "ok",
        "service": "ml",
        "artifact_path_configured": artifact_configured,
    }


class HealthHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        # Inherited logger writes method/path/status only — no headers or bodies.
        super().log_message(format, *args)

    def _send_json(self, code: int, payload: dict[str, str]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path in {"/health", "/health/", "/"}:
            try:
                self._send_json(200, _health_payload())
            except Exception:
                self._send_json(503, {"status": "unavailable", "service": "ml"})
            return
        self._send_json(404, {"status": "not_found", "service": "ml"})


def main() -> None:
    port = int(os.environ.get("ML_HEALTH_PORT", "8080"))
    host = os.environ.get("ML_HEALTH_HOST", "0.0.0.0")
    server = ThreadingHTTPServer((host, port), HealthHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
