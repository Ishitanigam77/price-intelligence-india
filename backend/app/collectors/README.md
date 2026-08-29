# app/collectors/

Orchestrates scheduled and on-demand data acquisition through the retailer adapter contract.

**Status**: implemented in **Phase 13 — Scalable Data Collection**.

Collection jobs are retailer-agnostic: they ask `RetailerRegistry` for enabled adapters that
support the needed operation, execute each retailer independently, and persist
`CollectionJob` / `CollectionError` rows. A failure in one retailer never aborts the others.

## Jobs

| Job | Adapter operation | Persistence |
|---|---|---|
| `product_search` | `search_products` | upsert products/listings + price snapshots |
| `product_refresh` | `get_product` | update known listings |
| `price_refresh` | `get_price` | new immutable `PriceSnapshot` rows |
| `availability_refresh` | `get_availability` | new snapshots using last-known observed prices |
| `sale_event_refresh` | stored observations | inferred `SaleEvent` windows (calculated) |

Only mock/approved adapters registered with `RetailerRegistry` are used. This package does not
scrape real retailers, bypass rate limits, `robots.txt`, authentication, or terms of service.

## Isolation, retries, timeouts, rate limits

- Each retailer runs in its own try/error path with its own `CollectionJob`.
- Retryable failures (timeout, rate limit, temporary) use exponential backoff capped by
  `COLLECTION_MAX_BACKOFF_SECONDS`. Permanent/validation errors are not retried.
- `COLLECTION_OPERATION_TIMEOUT_SECONDS` and `COLLECTION_RETAILER_TIMEOUT_SECONDS` bound hung
  calls so one retailer cannot block the worker indefinitely.
- Collection rate limiting is per retailer (token bucket). Retailer A's budget never blocks B.

## Idempotency

See `idempotency.py`. Logical runs share a stable `idempotency_key`; repeating a completed
SUCCESS/PARTIAL_SUCCESS job returns the existing row and does not duplicate products, prices,
availability observations, sale events, or job records.

## Metrics-ready names

`jobs_total`, `jobs_failed`, `jobs_successful`, `job_duration`, `retailer_health`,
`price_freshness` — recorded through the existing `MetricsSink` seam. No metrics platform is
introduced here.

## Workers

Celery tasks live in `app/workers/`. Broker and result backend are Redis URLs from the
environment (`CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`).
