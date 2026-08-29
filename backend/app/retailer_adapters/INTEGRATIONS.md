# Phase 14A — First real retailer integration batch

This document records the retailer selection for Phase 14A. Adapters are isolated packages
under `app/retailer_adapters/<slug>/`. The Phase 13 collection engine, comparison, matching,
pricing, sales, and recommendation modules are unchanged.

## Implemented (legitimate, documented integrations)

See each adapter README for endpoints, auth, rate limits, limitations, and live-E2E status.

| Retailer | Official source | Auth | Implementable? |
|---|---|---|---|
| **Amazon.in** | Amazon Associates Creators API (`www.amazon.in`) | OAuth 2.0 client credentials + Associates partner tag | Yes — documented catalog search and GetItems, documented 1 TPS / 8640 TPD initial cap |
| **Flipkart** | Flipkart Affiliate API 1.0 | `Fk-Affiliate-Id` + `Fk-Affiliate-Token` headers | Yes — documented keyword search (max 10) and product-id lookup, documented 20 calls/s |

**REAL RETAILER E2E: NOT TESTED — APPROVED API/CREDENTIALS NOT AVAILABLE.**

Fixture tests cover request construction, search, lookup, price, availability, normalization,
timeouts, HTTP 429, and malformed payloads without contacting either retailer.

## Evaluated and not implemented

Phase 14A implements only retailers with a clearly available, permitted, and sufficiently
documented integration path. The following were checked against official/affiliate developer
docs and **not** implemented:

| Retailer | Finding |
|---|---|
| Myntra | No public/official product catalog API. Affiliate presence is via third-party networks (link generation), not a documented product search/lookup API. |
| Nykaa | Nykaa Affiliate Program (NAP) documents manual sharable-link creation, not a product feed or search API. |
| Croma | Affiliate program is listed on third-party networks; no first-party product API/feed schema published by Croma. |
| Tata CLiQ | Affiliate program via third-party networks; no first-party documented product API. |
| Snapdeal | Historical affiliate feed docs are stale. Current developer surface is seller APIs (own inventory), not a public catalog for comparison. |
| ShopClues | Affiliate page says a CSV/API feed is provided after emailing the affiliate team; endpoint and schema are not published. Insufficient to implement. |
| Decathlon India | Public Decathlon developer APIs cover sport/activity data, not the India retail catalog. |
| eBay Browse API | Official, but India (`EBAY_IN`) is not a supported Browse API marketplace. Not an India-retailer integration. |
| Meesho / JioMart / BigBasket / Ajio / Reliance Digital | No clearly documented, permitted third-party product catalog API found. Seller/partner portals are not a substitute. |

Third-party scraping APIs, browser automation, and unofficial storefront JSON endpoints were
rejected under `RETAILER_ARCHITECTURE.md` §2.

## Default wiring

`RETAILER_ADAPTER_KINDS` still defaults to `mock`, so Phase 13 collection and product discovery
keep using the fixture-backed mock adapters unless an operator explicitly enables `integration`
and supplies credentials through the environment / Key Vault.
