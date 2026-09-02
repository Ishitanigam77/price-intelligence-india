# app/repositories/

Data access layer. Repositories expose domain-oriented read/write operations and hide
SQLAlchemy/query details from the domain and API layers.

**Status**: implemented in **Phase 1 — Core Domain Model & Database Foundation**.

`base.py` defines a generic `BaseRepository` (get by id, list, add, delete, and — added for the
FastAPI backend application foundation's paginated API list endpoints — `count`); one
repository per entity subclasses it and adds entity-specific lookups (e.g. `get_by_slug`,
`get_by_name`, `list_for_retailer`, `latest_for_retailer_product`, `get_by_type_and_value`,
`search_active_by_name`).
`PriceSnapshotRepository` deliberately has no update method — Price Observations are
immutable; corrections are new snapshots. `PriceAdjustmentRepository` stores promotional
adjustment provenance (coupon / payment discount / cashback) for the Phase 6 comparison
engine; it likewise has no update method. `SaleEventRepository` lists sale windows by type,
source, scope, and derived lifecycle status (Phase 9). User-owned repositories
(`UserRepository`, `WatchlistRepository`, `SavedProductRepository`, `TargetPriceRepository`,
`PriceAlertRepository`) always filter by `user_id` (Phase 12). `CollectionJobRepository` and
`CollectionErrorRepository` persist Phase 13 background collection status and sanitized
failures.

Consumed directly by `app/api/v1/` routes via the dependency providers in `app/api/deps.py`.
