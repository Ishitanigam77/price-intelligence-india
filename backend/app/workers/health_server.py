"""Optional HTTP liveness server for Celery workers.

Started only when `WORKER_HEALTH_HTTP` is true so unit tests and eager Celery runs
do not bind a port. Does not expose secrets or configuration values.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.core.config import get_settings
from app.core.redis import check_redis_connection, create_redis_client
from app.observability.logging import get_logger
from app.workers.health import worker_liveness_payload, worker_readiness_payload

logger = get_logger(__name__)

_server: ThreadingHTTPServer | None = None
_thread: threading.Thread | None = None


class WorkerHealthHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        super().log_message(format, *args)

    def _send_json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in {"/health", "/health/", "/health/live", "/"}:
            self._send_json(200, worker_liveness_payload())
            return
        if path in {"/health/ready", "/ready"}:
            try:
                broker_ok = check_redis_connection(create_redis_client())
            except Exception:
                broker_ok = False
            payload = worker_readiness_payload(broker_ok=broker_ok)
            code = 200 if payload["status"] == "ok" else 503
            self._send_json(code, payload)
            return
        self._send_json(404, {"status": "not_found", "service": "worker"})


def start_worker_health_server() -> ThreadingHTTPServer | None:
    """Start the probe server in a daemon thread. Idempotent. Never raises to the worker."""
    global _server, _thread
    settings = get_settings()
    if not settings.worker_health_http:
        return None
    if _server is not None:
        return _server
    try:
        server = ThreadingHTTPServer(
            (settings.worker_health_host, settings.worker_health_port),
            WorkerHealthHandler,
        )
    except Exception:
        logger.exception(
            "worker.health_server_failed",
            extra={"operation": "start_health_server", "status": "error", "service": "worker"},
        )
        return None
    thread = threading.Thread(target=server.serve_forever, name="worker-health", daemon=True)
    thread.start()
    _server = server
    _thread = thread
    logger.info(
        "worker.health_server_started",
        extra={
            "operation": "start_health_server",
            "status": "ok",
            "service": "worker",
            "environment": settings.environment,
        },
    )
    return server
