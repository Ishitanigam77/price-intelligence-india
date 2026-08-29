"""Shared HTTP test doubles for Phase 14A retailer adapters.

No live network: handlers run inside `httpx.MockTransport`.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx

MockResponse = (
    Callable[[httpx.Request], httpx.Response] | httpx.Response | dict[str, Any] | bytes | int
)


class RecordingHandler:
    """Dispatch mock responses by URL substring and record outbound requests."""

    def __init__(self, routes: dict[str, MockResponse]) -> None:
        self.requests: list[httpx.Request] = []
        self._routes = routes

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = str(request.url)
        for fragment, response in self._routes.items():
            if fragment in url:
                return self._materialize(response, request)
        return httpx.Response(404, json={"error": "no mock route matched"})

    def _materialize(
        self,
        response: MockResponse,
        request: httpx.Request,
    ) -> httpx.Response:
        if callable(response) and not isinstance(response, httpx.Response):
            return response(request)  # type: ignore[return-value]
        if isinstance(response, httpx.Response):
            return response
        if isinstance(response, int):
            return httpx.Response(response)
        if isinstance(response, bytes):
            return httpx.Response(200, content=response)
        return httpx.Response(200, json=response)

    def json_bodies(self) -> list[Any]:
        bodies: list[Any] = []
        for request in self.requests:
            if not request.content:
                continue
            try:
                bodies.append(json.loads(request.content.decode("utf-8")))
            except json.JSONDecodeError:
                bodies.append(request.content.decode("utf-8"))
        return bodies


def mock_client(handler: RecordingHandler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))
