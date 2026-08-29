# Amazon.in adapter

Phase 14A real retailer integration. Isolated behind `RetailerAdapter`. The Phase 13
collection engine and comparison modules are not modified for this retailer.

## Data source

Official **Amazon Associates Creators API** (successor to Product Advertising API 5.0) for
the India marketplace `www.amazon.in`.

- Documentation: https://affiliate-program.amazon.com/creatorsapi/docs/en-us/introduction
- India rates: https://affiliate-program.amazon.in/creatorsapi/docs/en-us/concepts/api-rates
- Integration type: official affiliate API (`source_type=affiliate_feed`)

## Endpoints

| Purpose | Method | URL |
|---|---|---|
| OAuth token | `POST` | `https://api.amazon.co.uk/auth/o2/token` (credential version 3.2, EU/IN region) |
| Search | `POST` | `https://creatorsapi.amazon/catalog/v1/searchItems` |
| Lookup / price / availability | `POST` | `https://creatorsapi.amazon/catalog/v1/getItems` |

Header `x-marketplace: www.amazon.in` and body field `marketplace: www.amazon.in` are required.
Search is capped at 10 items per request by the API (`itemCount` 1–10). GetItems accepts up to
10 ASINs per call; this adapter requests one ASIN per lookup.

## Authentication

OAuth 2.0 client credentials (`grant_type=client_credentials`, scope `creatorsapi::default`)
using a Credential ID and Credential Secret issued from Associates Central. Access tokens are
cached until shortly before the documented 3600s expiry. Every catalog call also sends the
Associates `partnerTag`.

Environment variables (never committed; Azure Key Vault in deployed environments):

| Variable | Role |
|---|---|
| `RETAILER_AMAZON_IN_CREDENTIAL_ID` | OAuth client id |
| `RETAILER_AMAZON_IN_CREDENTIAL_SECRET` | OAuth client secret |
| `RETAILER_AMAZON_IN_PARTNER_TAG` | Associates tracking id (e.g. `yoursite-21`) |

Optional non-secret overrides: `RETAILER_AMAZON_IN_TIMEOUT_SECONDS`,
`RETAILER_AMAZON_IN_MAX_ATTEMPTS`, `RETAILER_AMAZON_IN_REQUESTS_PER_MINUTE`,
`RETAILER_AMAZON_IN_ENABLED`.

## Rate limits

Documented initial allowance: **1 request per second (1 TPS)** and **8640 requests per day
(TPD)** for the first 30 days, then scaled by referred shipped revenue (max 10 TPS). HTTP
`429 TooManyRequests` is treated as rate-limited and retried with backoff. This adapter paces
at 60 requests/minute, burst size 1, max concurrency 1 — inside the published 1 TPS cap.

Access is revoked if the Associates account has no qualifying referred sales for 30 consecutive
days. New accounts need at least 10 qualifying sales in 30 days before Creators API access is
granted.

## Known limitations

- Prices and availability come from `offersV2` (buy-box listing when flagged). `effective_price`
  is left unset; deriving payable totals is the pricing engine's job.
- SearchIndex coverage is a fixed slug→index map; Amazon browse-node trees are not fully
  mirrored.
- Out-of-stock items are requested via `availability=IncludeOutOfStock`.
- Affiliate detail URLs retain Creators API query parameters (required by Amazon for
  attribution); they are stored as `source_url`.
- No scraping, Playwright, or unofficial catalogue endpoints are used.

## Live E2E

**REAL RETAILER E2E: NOT TESTED — APPROVED API/CREDENTIALS NOT AVAILABLE.**

Tests use fixture payloads shaped like the documented Creators API responses. They do not
contact Amazon.
