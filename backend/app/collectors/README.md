# app/collectors/

Orchestrates data acquisition: schedules/triggers retailer adapters, handles retries and
health/status recording, and hands raw results to the normalization pipeline.

**Status**: empty scaffold. The adapter framework (timeouts, retries, health, registry) now
lives in `app/retailer_adapters/`. Collector orchestration — Celery beat schedules, on-demand
collection jobs, persistence of observations — is not implemented in Phase 2 and must not
be inferred from the adapter framework's existence.
