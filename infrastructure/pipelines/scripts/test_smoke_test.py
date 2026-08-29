"""Unit tests for post-deploy smoke probes (no live network)."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from smoke_test import SmokeFailure, main, parse_args, run


def _ok(url: str, timeout: float) -> tuple[int, bytes]:  # noqa: ARG001
    if url.endswith("/health") or url.endswith("/health/ready"):
        return 200, json.dumps({"status": "ok"}).encode()
    return 404, b"{}"


def test_parse_args_reads_backend_url() -> None:
    args = parse_args(["--backend-url", "http://localhost:8000"])
    assert args.backend_url == "http://localhost:8000"


def test_run_fails_without_backend_url() -> None:
    args = parse_args(["--backend-url", ""])
    with pytest.raises(SmokeFailure, match="backend URL is required"):
        run(args)


def test_run_passes_when_all_endpoints_ok() -> None:
    args = parse_args(
        [
            "--backend-url",
            "http://backend.example",
            "--frontend-url",
            "http://frontend.example",
            "--ml-url",
            "http://ml.example",
        ]
    )
    with patch("smoke_test._request", side_effect=_ok):
        run(args)


def test_run_fails_on_http_error() -> None:
    args = parse_args(["--backend-url", "http://backend.example"])

    def _fail(url: str, timeout: float) -> tuple[int, bytes]:  # noqa: ARG001
        return 503, json.dumps({"status": "degraded"}).encode()

    with patch("smoke_test._request", side_effect=_fail), pytest.raises(SmokeFailure, match="HTTP 503"):
        run(args)


def test_main_returns_nonzero_on_failure() -> None:
    with patch("smoke_test._request", return_value=(500, b"nope")):
        assert main(["--backend-url", "http://backend.example"]) == 1
