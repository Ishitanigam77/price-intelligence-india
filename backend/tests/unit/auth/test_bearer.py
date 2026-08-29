"""Unit tests for bearer-token extraction."""

from starlette.requests import Request

from app.auth.dependencies import extract_bearer_token


def _request(authorization: str | None) -> Request:
    headers = []
    if authorization is not None:
        headers.append((b"authorization", authorization.encode("latin-1")))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": headers,
        "client": ("test", 123),
        "server": ("test", 80),
    }
    return Request(scope)


def test_extracts_bearer_token() -> None:
    assert extract_bearer_token(_request("Bearer abc.def.ghi")) == "abc.def.ghi"


def test_bearer_is_case_insensitive() -> None:
    assert extract_bearer_token(_request("bearer token-value")) == "token-value"


def test_missing_header_returns_none() -> None:
    assert extract_bearer_token(_request(None)) is None


def test_non_bearer_scheme_returns_none() -> None:
    assert extract_bearer_token(_request("Basic abc")) is None


def test_empty_bearer_returns_none() -> None:
    assert extract_bearer_token(_request("Bearer   ")) is None
