# Flipkart adapter

Phase 14A real retailer integration. Isolated behind `RetailerAdapter`. The Phase 13
collection engine and comparison modules are not modified for this retailer.

## Data source

Official **Flipkart Affiliate API 1.0** (Product APIs: keyword search and product-id lookup).

- Documentation: https://affiliate.flipkart.com/api-docs/af_prod_ref.html
- FAQ (rate limits, search cap): https://affiliate.flipkart.com/api-docs/af_faq.html
- Terms: https://affiliate.flipkart.com/api-docs/af_tou.html
- Integration type: official affiliate API (`source_type=affiliate_feed`)

## Endpoints

| Purpose | Method | URL |
|---|---|---|
| Keyword search | `GET` | `https://affiliate-api.flipkart.net/affiliate/1.0/search.json` |
| Product lookup / price / availability | `GET` | `https://affiliate-api.flipkart.net/affiliate/1.0/product.json` |

Search query parameters: `query` (keywords), `resultCount` (maximum **10**, documented).
Lookup query parameter: `id` (Flipkart product id / FSN).

Category product feeds and CSV dumps exist in the same API family but are not used by this
adapter (search + per-id refresh cover the Phase 13 collection operations).

## Authentication

HTTPS request headers (from https://affiliate.flipkart.com/api-docs/af_register.html):

- `Fk-Affiliate-Id`: Affiliate Tracking ID
- `Fk-Affiliate-Token`: Affiliate API Token (one active token per affiliate account)

Environment variables (never committed; Azure Key Vault in deployed environments):

| Variable | Role |
|---|---|
| `RETAILER_FLIPKART_AFFILIATE_ID` | Affiliate tracking id |
| `RETAILER_FLIPKART_AFFILIATE_TOKEN` | Affiliate API token |

Optional non-secret overrides: `RETAILER_FLIPKART_TIMEOUT_SECONDS`,
`RETAILER_FLIPKART_MAX_ATTEMPTS`, `RETAILER_FLIPKART_REQUESTS_PER_MINUTE`,
`RETAILER_FLIPKART_ENABLED`.

## Rate limits

Documented: **20 calls per second per affiliate**. Exceeding the published volume may lead to
suspension under the API terms. HTTP 429 is treated as rate-limited and retried with backoff.
This adapter paces at 120 requests/minute (2/s), burst size 1, max concurrency 1 — well inside
the published 20/s cap.

Product-feed listing URLs expire within 10 hours; this adapter uses the stable search and
product-id endpoints instead of expiring feed URLs.

## Known limitations

- Keyword search returns at most 10 products. There is no category filter on the search
  endpoint; category slugs are used as keywords when no free-text query is supplied.
- Flipkart product ids are retailer SKUs, not GTINs. The documented product payload does not
  reliably expose EAN/UPC, so `get_product_identifiers` is not declared.
- `effective_price` is left unset. `flipkartSellingPrice` is mapped to `displayed_price` and
  `maximumRetailPrice` to `mrp` when present.
- `inStock` may be `null` in documented examples; that maps to availability `unknown`.
- Affiliate `productUrl` values include the tracking id appended by Flipkart; they are stored
  as `source_url`.
- No scraping, Playwright, or unofficial catalogue endpoints are used.

## Live E2E

**REAL RETAILER E2E: NOT TESTED — APPROVED API/CREDENTIALS NOT AVAILABLE.**

Tests use fixture payloads shaped like the documented Affiliate API responses. They do not
contact Flipkart.
