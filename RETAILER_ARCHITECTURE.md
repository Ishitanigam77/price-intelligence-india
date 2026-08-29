# RETAILER_ARCHITECTURE.md — PriceRadar India

> This document defines how retailers are integrated so that the network can grow from a
> handful of retailers to 100+ without changes to the core comparison, matching, or pricing
> engines. The common adapter interface, registry, configuration, standardized models, three
> fixture-backed mock adapters, and the Phase 14A Amazon.in / Flipkart adapters are implemented
> (see `backend/app/retailer_adapters/`). Mock adapters remain in-process fixtures. Real
> adapters call official affiliate APIs only when environment credentials are present.

## 1. Design Goal

**Adding retailer #50 or #100 must not require rewriting the core comparison engine.**

This is achieved by ensuring:

- Every retailer's integration lives entirely behind a common **Retailer Adapter** interface.
- The core engine (normalization, matching, pricing, sale-event intelligence, recommendation)
  only ever depends on that interface — never on a specific retailer's API shape, feed format,
  or website structure.
- Retailer-specific quirks (auth, pagination, field names, currency formatting, rate limits)
  are handled entirely inside that retailer's adapter package.

## 2. Legitimate Data Acquisition Policy

This is a hard constraint on every retailer integration, not a preference:

- **Allowed**: official retailer/marketplace APIs, affiliate/partner APIs or feeds, product
  data feeds (e.g. CSV/XML/JSON feeds provided under an affiliate or partner agreement), and
  other integrations explicitly permitted by the retailer's terms.
- **Never allowed**, under any circumstance:
  - Bypassing CAPTCHA or anti-bot systems.
  - Bypassing authentication or access controls.
  - Exceeding or evading published rate limits.
  - Ignoring `robots.txt` restrictions.
  - Violating a retailer's terms of service.
  - Fabricating, estimating, or inferring a retailer's price/availability when no legitimate
    source provided it.
- Playwright (browser automation) is only used where a *specific, permitted* integration
  genuinely requires it (e.g. an authorized partner portal without an API) — never as a
  generic scraping tool and never to defeat anti-bot protections.
- Every retailer integration must record which lawful access method it uses (official API,
  affiliate feed, product feed, other permitted integration) as part of its adapter metadata,
  and this is what populates the `source_type` field on every Price Observation.

## 3. Retailer Adapter Interface (Conceptual Contract)

Each retailer adapter will implement a common interface responsible for:

1. **Identity & capability metadata** — retailer name, category coverage, supported source
   type (official API / affiliate feed / product feed / other permitted integration), rate
   limit policy, and health/status reporting.
2. **Discovery** — given a search term or category, return candidate raw listings from that
   retailer's legitimate source.
3. **Listing fetch** — given a known listing reference, fetch its current raw data (price,
   availability, MRP if exposed, etc.).
4. **Raw-to-common mapping** — translate the retailer's native response shape into the common
   raw listing shape the normalization pipeline expects (field names may differ per retailer;
   this is where that's reconciled).
5. **Health reporting** — expose whether the adapter's most recent calls succeeded, latency,
   and error state, feeding the retailer health/data-freshness features of the product.

The adapter interface itself is implemented in `backend/app/retailer_adapters/base/`. Mock
adapters in `mock_retailer_a/`, `mock_retailer_b/`, and `mock_retailer_c/` validate the
contract against invented fixture data. Phase 14A adds `amazon_in/` and `flipkart/` using
documented official affiliate APIs (see `backend/app/retailer_adapters/INTEGRATIONS.md`).

## 4. Directory Convention (Target)

```
backend/app/retailer_adapters/
  base/                     # common interface / abstract adapter, shared types
  <retailer_slug>/          # one package per retailer, e.g. "example_retailer"
    adapter.py              # implements the common interface
    mapping.py              # raw → common field mapping
    config.py               # retailer-specific configuration (endpoints, rate limits)
    tests/                  # adapter-level tests using recorded fixtures
```

Core modules (`normalization/`, `matching/`, `pricing/`, `sales/`, `recommendation/`) never
import from a specific `retailer_adapters/<retailer_slug>/` package. They only depend on the
common interface and the common raw/normalized data shapes.

## 5. Retailer Onboarding Checklist (Target Process)

When a new retailer is added (Phase 10 onward), the process is expected to be:

1. Confirm a legitimate access method exists (official API, affiliate/partner feed, or other
   permitted integration) and document it.
2. Implement the retailer's adapter package, satisfying the common interface.
3. Add adapter-level tests using recorded/fixture responses (no live calls in CI).
4. Register the adapter with the collector orchestration layer.
5. Verify retailer health reporting appears correctly in monitoring.
6. No changes to `normalization/`, `matching/`, `pricing/`, `sales/`, or `recommendation/`
   should be necessary. If they are, that's a signal the adapter interface needs to evolve —
   handled as its own deliberate change, not a one-off hack for a single retailer.

## 6. Price Observation Contract

Every Price Observation produced by any adapter, regardless of retailer, must carry:

| Field | Description |
|---|---|
| `retailer` | Which retailer this observation came from |
| `seller` | The seller fulfilling the listing (may equal the retailer for first-party listings) |
| `source_url` | The URL/reference the data was observed from |
| `observed_at` | Timestamp of observation |
| `displayed_price` | The price as shown by the source |
| `mrp` | Manufacturer's stated maximum retail price, where available |
| `effective_price` | Calculated price after verified discounts/fees, where calculable |
| `availability` | In stock / out of stock / limited / unknown |
| `source_type` | official_api / affiliate_feed / product_feed / other_permitted |
| `confidence` | Data freshness/confidence indicator |

This contract is what makes the core engine retailer-agnostic: no matter how different two
retailers' native APIs are, they both ultimately populate the same Price Observation shape.

## 7. Explicit Non-Goals

- Mock adapters use invented fixture data and `*.example.test` URLs; they are not stand-ins
  for a named retailer.
- This document does not authorize scraping. Every real adapter must be justified by a
  legitimate access method before implementation begins. Phase 14A adapters and the skipped
  retailers are listed in `backend/app/retailer_adapters/INTEGRATIONS.md`.
