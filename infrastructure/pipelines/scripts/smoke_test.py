#!/usr/bin/env python3
"""Post-deployment smoke tests against real application health endpoints.

Fails the process (exit 1) if any required endpoint is missing, returns a non-success
status, or times out. Does not invent application routes — only probes endpoints that exist
in this repository:

  Backend (FastAPI):
    GET /health
    GET /health/ready
    GET /api/v1/health
    GET /api/v1/health/ready

  Frontend (Next.js):
    GET /health

  ML container (stdlib liveness server):
    GET /health

No credentials are logged. Optional bearer tokens are accepted via environment variables for
future protected probes but are not printed.

Usage:
  python infrastructure/pipelines/scripts/smoke_test.py --backend-url https://api.example
  python infrastructure/pipelines/scripts/smoke_test.py \\
      --backend-url http://localhost:8000 \\
      --frontend-url http://localhost:3000 \\
      --ml-url http://localhost:8080
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

DEFAULT_TIMEOUT_SECONDS = 10


class SmokeFailure(Exception):
    """One smoke probe did not meet the success criteria."""


def _request(url: str, timeout: float) -> tuple[int, bytes]:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.status), response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp is not None else b""
        return int(exc.code), body
    except urllib.error.URLError as exc:
        raise SmokeFailure(f"GET {url} failed: {exc.reason!s}") from exc


def _must_ok(name: str, url: str, timeout: float, *, expect_json_status: str | None = "ok") -> None:
    status, body = _request(url, timeout)
    if status < 200 or status >= 300:
        raise SmokeFailure(f"{name}: GET {url} returned HTTP {status}")
    if expect_json_status is None:
        return
    try:
        payload: Any = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SmokeFailure(f"{name}: GET {url} did not return JSON") from exc
    if not isinstance(payload, dict) or payload.get("status") != expect_json_status:
        raise SmokeFailure(f"{name}: GET {url} JSON status was not {expect_json_status!r}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PriceRadar India post-deploy smoke tests.")
    parser.add_argument(
        "--backend-url",
        default=os.environ.get("SMOKE_BACKEND_URL", "").rstrip("/"),
        help="Backend origin, e.g. https://ca-backend.azurecontainerapps.io",
    )
    parser.add_argument(
        "--frontend-url",
        default=os.environ.get("SMOKE_FRONTEND_URL", "").rstrip("/"),
        help="Frontend origin. Optional; skipped when empty.",
    )
    parser.add_argument(
        "--ml-url",
        default=os.environ.get("SMOKE_ML_URL", "").rstrip("/"),
        help="ML liveness origin. Optional; skipped when empty.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=float(os.environ.get("SMOKE_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))),
    )
    parser.add_argument(
        "--skip-readiness",
        action="store_true",
        help="Skip /health/ready probes (liveness only). Not used in the default CD pipeline.",
    )
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> None:
    if not args.backend_url:
        raise SmokeFailure("backend URL is required (--backend-url or SMOKE_BACKEND_URL).")

    timeout = args.timeout_seconds
    _must_ok("backend-liveness", f"{args.backend_url}/health", timeout)
    _must_ok("backend-v1-liveness", f"{args.backend_url}/api/v1/health", timeout)
    if not args.skip_readiness:
        _must_ok("backend-readiness", f"{args.backend_url}/health/ready", timeout)
        _must_ok("backend-v1-readiness", f"{args.backend_url}/api/v1/health/ready", timeout)

    if args.frontend_url:
        _must_ok("frontend-liveness", f"{args.frontend_url}/health", timeout)

    if args.ml_url:
        _must_ok("ml-liveness", f"{args.ml_url}/health", timeout)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        run(args)
    except SmokeFailure as exc:
        print(f"smoke_test FAILED: {exc}", file=sys.stderr)
        return 1
    print("smoke_test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
