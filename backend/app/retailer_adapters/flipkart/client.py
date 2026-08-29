"""HTTP client for the Flipkart Affiliate API 1.0.

Official documentation: https://affiliate.flipkart.com/api-docs/af_prod_ref.html

Auth: headers `Fk-Affiliate-Id` and `Fk-Affiliate-Token` on HTTPS GET requests.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.retailer_adapters.base.http import request_json, require_mapping
from app.retailer_adapters.flipkart.auth import FlipkartCredentials
from app.retailer_adapters.flipkart.config import DEFAULT_API_BASE_URL, RETAILER_ID


class FlipkartApiClient:
    """Thin Affiliate API client. The token is held in memory and never logged."""

    def __init__(
        self,
        credentials: FlipkartCredentials,
        *,
        http_client: httpx.AsyncClient,
        timeout_seconds: float,
        api_base_url: str = DEFAULT_API_BASE_URL,
    ) -> None:
        self._credentials = credentials
        self._http = http_client
        self._timeout_seconds = timeout_seconds
        self._api_base_url = api_base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {
            "Fk-Affiliate-Id": self._credentials.affiliate_id,
            "Fk-Affiliate-Token": self._credentials.affiliate_token,
            "Accept": "application/json",
        }

    async def search(self, *, query: str, result_count: int, operation: str) -> dict[str, Any]:
        payload = await request_json(
            self._http,
            method="GET",
            url=f"{self._api_base_url}/1.0/search.json",
            retailer_id=RETAILER_ID,
            operation=operation,
            timeout_seconds=self._timeout_seconds,
            headers=self._headers(),
            params={"query": query, "resultCount": max(1, min(result_count, 10))},
        )
        return require_mapping(payload, retailer_id=RETAILER_ID, operation=operation)

    async def get_product(self, *, product_id: str, operation: str) -> dict[str, Any]:
        payload = await request_json(
            self._http,
            method="GET",
            url=f"{self._api_base_url}/1.0/product.json",
            retailer_id=RETAILER_ID,
            operation=operation,
            timeout_seconds=self._timeout_seconds,
            headers=self._headers(),
            params={"id": product_id},
            not_found_is_missing=True,
        )
        return require_mapping(payload, retailer_id=RETAILER_ID, operation=operation)
