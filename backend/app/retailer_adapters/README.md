# app/retailer_adapters/

Home of the common retailer adapter interface and one package per retailer. This is the
isolation boundary that lets the platform scale to 100+ retailers without changing core
comparison/matching/pricing logic. See `../../../RETAILER_ARCHITECTURE.md` for the full
contract and the legitimate-data-acquisition policy.

**Status**: **Phase 14A — first real retailer integrations** on top of the Phase 2 adapter
framework. `base/` is unchanged in contract. Mock adapters remain. Real integrations live in
their own packages (`amazon_in/`, `flipkart/`) and are discovered as `AdapterKind.INTEGRATION`.
See `INTEGRATIONS.md` for selection notes and each package README for API details.

## Layout

```
base/                     # retailer-agnostic framework
  interface.py            # RetailerAdapter ABC (timeout/retry/rate-limit/logging/metrics)
  models.py               # RetailerProduct, NormalizedProduct, PriceObservation, ...
  config.py               # capabilities, timeout, retry policy, rate-limit config
  errors.py               # retailer-agnostic error taxonomy
  execution.py            # reusable timeout + retry + instrumentation
  rate_limit.py           # per-retailer pacing (stay within published limits)
  http.py                 # JSON HTTP helper (timeouts; maps 429/5xx/auth to framework errors)
  registry.py             # register / discover / enable / disable / health-check
  discovery.py            # package-convention discovery of adapter factories
  fleet.py                # retailer-agnostic fan-out over registered adapters
  metrics.py              # MetricsSink extension points (no monitoring platform)
amazon_in/                # Amazon.in Associates Creators API (official affiliate API)
flipkart/                 # Flipkart Affiliate API 1.0 (official affiliate API)
mock_retailer_a/          # official-API shaped mock (paise amounts, GTINs, first-party)
mock_retailer_b/          # affiliate-feed shaped mock (string amounts, MPNs, marketplace)
mock_retailer_c/          # product-feed shaped mock (nested entries, no identifiers)
```

Adding a retailer means implementing `RetailerAdapter` and registering it. Process startup
(`app/retailer_adapters/wiring.py`) discovers adapter packages by convention and registers
them with the `RetailerRegistry`; product discovery never imports a specific adapter package.

Mock adapters read in-process fixtures; they make no network calls and represent no real
retailer. Real adapters use only the legitimate access method documented in their README.
They read credentials from the environment and do not perform live calls in tests.
