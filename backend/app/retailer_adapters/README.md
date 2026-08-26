# app/retailer_adapters/

Home of the common retailer adapter interface and one package per retailer. This is the
isolation boundary that lets the platform scale to 100+ retailers without changing core
comparison/matching/pricing logic. See `../../../RETAILER_ARCHITECTURE.md` for the full
contract and the legitimate-data-acquisition policy.

**Status**: **Phase 2 — Retailer Adapter Framework** implemented. The reusable framework
(`base/`) and three fixture-backed mock adapters exist. No real retailer integrations, no
scraping, and no collector/Celery orchestration are included in this phase.

## Layout

```
base/                     # retailer-agnostic framework
  interface.py            # RetailerAdapter ABC (timeout/retry/rate-limit/logging/metrics)
  models.py               # RetailerProduct, NormalizedProduct, PriceObservation, ...
  config.py               # capabilities, timeout, retry policy, rate-limit config
  errors.py               # retailer-agnostic error taxonomy
  execution.py            # reusable timeout + retry + instrumentation
  rate_limit.py           # per-retailer pacing (stay within published limits)
  registry.py             # register / discover / enable / disable / health-check
  discovery.py            # package-convention discovery of adapter factories
  fleet.py                # retailer-agnostic fan-out over registered adapters
  metrics.py              # MetricsSink extension points (no monitoring platform)
mock_retailer_a/          # official-API shaped mock (paise amounts, GTINs, first-party)
mock_retailer_b/          # affiliate-feed shaped mock (string amounts, MPNs, marketplace)
mock_retailer_c/          # product-feed shaped mock (nested entries, no identifiers)
```

Adding a retailer means implementing `RetailerAdapter` and registering it. Process startup
(`app/retailer_adapters/wiring.py`) discovers adapter packages by convention and registers
them with the `RetailerRegistry`; product discovery never imports a specific adapter package.

Mock adapters read in-process fixtures; they make no network calls and represent no real
retailer. Real integrations are a later phase and must use a legitimate access method.
