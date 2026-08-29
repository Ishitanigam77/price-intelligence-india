"""HTTP client for the Amazon Associates Creators API (India marketplace).

Official documentation:
https://affiliate-program.amazon.com/creatorsapi/docs/en-us/introduction

Auth: OAuth 2.0 client-credentials against the regional token endpoint, then
`Authorization: Bearer` on `https://creatorsapi.amazon/catalog/v1/{searchItems,getItems}`
with `x-marketplace: www.amazon.in`.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from typing import Any

import httpx

from app.retailer_adapters.amazon_in.auth import AmazonInCredentials
from app.retailer_adapters.amazon_in.config import (
    DEFAULT_API_BASE_URL,
    DEFAULT_LANGUAGE,
    DEFAULT_MARKETPLACE,
    DEFAULT_TOKEN_URL,
    RETAILER_ID,
)
from app.retailer_adapters.base.errors import (
    InvalidRetailerResponseError,
    RateLimitExceededError,
    TemporaryRetailerFailureError,
)
from app.retailer_adapters.base.http import request_json, require_mapping

#: Creators API resource names requested for search and item lookup.
CATALOG_RESOURCES: tuple[str, ...] = (
    "itemInfo.title",
    "itemInfo.byLineInfo",
    "itemInfo.classifications",
    "itemInfo.productInfo",
    "itemInfo.externalIds",
    "itemInfo.manufactureInfo",
    "browseNodeInfo.browseNodes",
    "offersV2.listings.price",
    "offersV2.listings.availability",
    "offersV2.listings.merchantInfo",
    "offersV2.listings.isBuyBoxWinner",
    "parentASIN",
)

#: Maps this adapter's category slugs onto Creators API SearchIndex values for India.
SEARCH_INDEX_BY_CATEGORY: dict[str, str] = {
    "mobiles": "Electronics",
    "electronics": "Electronics",
    "audio": "Electronics",
    "computers": "Computers",
    "home-appliances": "Appliances",
    "fashion": "Fashion",
    "beauty": "Beauty",
    "grocery": "GroceryAndGourmetFood",
    "books": "Books",
    "sports": "SportsAndOutdoors",
    "toys": "ToysAndGames",
    "automotive": "Automotive",
    "home-and-kitchen": "HomeAndKitchen",
}

_TOKEN_REFRESH_SKEW_SECONDS = 60.0


class AmazonInApiClient:
    """Thin Creators API client. Credentials are held in memory and never logged."""

    def __init__(
        self,
        credentials: AmazonInCredentials,
        *,
        http_client: httpx.AsyncClient,
        timeout_seconds: float,
        api_base_url: str = DEFAULT_API_BASE_URL,
        token_url: str = DEFAULT_TOKEN_URL,
        marketplace: str = DEFAULT_MARKETPLACE,
        language: str = DEFAULT_LANGUAGE,
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        self._credentials = credentials
        self._http = http_client
        self._timeout_seconds = timeout_seconds
        self._api_base_url = api_base_url.rstrip("/")
        self._token_url = token_url
        self._marketplace = marketplace
        self._language = language
        self._access_token: str | None = None
        self._token_expires_at = 0.0
        self._monotonic = monotonic or time.monotonic

    async def search_items(
        self,
        *,
        keywords: str,
        search_index: str | None,
        item_count: int,
        operation: str,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "keywords": keywords,
            "itemCount": max(1, min(item_count, 10)),
            "marketplace": self._marketplace,
            "partnerTag": self._credentials.partner_tag,
            "languagesOfPreference": [self._language],
            "resources": list(CATALOG_RESOURCES),
            "availability": "IncludeOutOfStock",
        }
        if search_index:
            body["searchIndex"] = search_index
        return await self._catalog_post("searchItems", body, operation=operation)

    async def get_items(self, *, asins: tuple[str, ...], operation: str) -> dict[str, Any]:
        body: dict[str, Any] = {
            "itemIds": list(asins),
            "itemIdType": "ASIN",
            "marketplace": self._marketplace,
            "partnerTag": self._credentials.partner_tag,
            "languagesOfPreference": [self._language],
            "resources": list(CATALOG_RESOURCES),
        }
        return await self._catalog_post("getItems", body, operation=operation)

    async def ensure_access_token(self, *, operation: str) -> str:
        """Return a cached bearer token, refreshing when close to expiry."""
        now = self._monotonic()
        if self._access_token and now < (self._token_expires_at - _TOKEN_REFRESH_SKEW_SECONDS):
            return self._access_token
        payload = await request_json(
            self._http,
            method="POST",
            url=self._token_url,
            retailer_id=RETAILER_ID,
            operation=operation,
            timeout_seconds=self._timeout_seconds,
            headers={"Content-Type": "application/json"},
            json_body={
                "grant_type": "client_credentials",
                "client_id": self._credentials.credential_id,
                "client_secret": self._credentials.credential_secret,
                "scope": "creatorsapi::default",
            },
        )
        mapping = require_mapping(payload, retailer_id=RETAILER_ID, operation=operation)
        token = mapping.get("access_token")
        if not isinstance(token, str) or not token.strip():
            raise InvalidRetailerResponseError(
                "The token endpoint did not return an access token.",
                retailer_id=RETAILER_ID,
                operation=operation,
            )
        expires_in = mapping.get("expires_in", 3600)
        try:
            ttl = float(expires_in)
        except (TypeError, ValueError):
            ttl = 3600.0
        self._access_token = token.strip()
        self._token_expires_at = now + max(ttl, 0.0)
        return self._access_token

    async def _catalog_post(
        self, path: str, body: Mapping[str, Any], *, operation: str
    ) -> dict[str, Any]:
        token = await self.ensure_access_token(operation=operation)
        payload = await request_json(
            self._http,
            method="POST",
            url=f"{self._api_base_url}/catalog/v1/{path}",
            retailer_id=RETAILER_ID,
            operation=operation,
            timeout_seconds=self._timeout_seconds,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "x-marketplace": self._marketplace,
            },
            json_body=body,
        )
        mapping = require_mapping(payload, retailer_id=RETAILER_ID, operation=operation)
        _raise_for_creators_errors(mapping, operation=operation)
        return mapping


def _raise_for_creators_errors(payload: dict[str, Any], *, operation: str) -> None:
    """Translate Creators API error objects on an otherwise-decoded JSON body."""
    errors = payload.get("errors")
    if not isinstance(errors, list) or not errors:
        return
    codes = [
        str(entry.get("code"))
        for entry in errors
        if isinstance(entry, dict) and entry.get("code")
    ]
    if any(code in {"TooManyRequests", "RequestThrottled"} for code in codes):
        raise RateLimitExceededError(
            "The source signalled that its published rate limit was reached.",
            retailer_id=RETAILER_ID,
            operation=operation,
        )
    if any(code in {"InternalFailure", "InternalError"} for code in codes):
        raise TemporaryRetailerFailureError(
            "The source returned a transient server error.",
            retailer_id=RETAILER_ID,
            operation=operation,
        )


def search_index_for(category: str | None) -> str | None:
    """Map a category slug to a Creators API SearchIndex, if this adapter covers it."""
    if category is None:
        return None
    return SEARCH_INDEX_BY_CATEGORY.get(category)
