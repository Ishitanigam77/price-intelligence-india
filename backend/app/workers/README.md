# app/workers/

Celery application, task definitions, and optional Beat schedules for collection jobs.

**Status**: implemented in **Phase 13 — Scalable Data Collection**.

- `celery_app.py` — Celery app factory. Broker/result backend URLs come from environment
  variables and are never logged.
- `celery_config.py` — worker concurrency, task time limits, JSON serialization, optional Beat.
- `tasks.py` — five collection tasks. Each builds a `RetailerRegistry` via
  `build_retailer_registry` and runs `CollectionOrchestrator`. No named retailer imports.

Notification dispatch, billing, and unrelated jobs are **not** implemented here.

## Run a worker (local)

```bash
cd backend
celery -A app.workers.celery_app worker --loglevel=INFO
```

Optional scheduler (disabled unless `COLLECTION_BEAT_ENABLED=true`):

```bash
celery -A app.workers.celery_app beat --loglevel=INFO
```
