# app/repositories/

Data access layer. Repositories expose domain-oriented read/write operations and hide
SQLAlchemy/query details from the domain and API layers.

**Status**: implemented in **Phase 1 — Core Domain Model & Database Foundation**.

`base.py` defines a generic `BaseRepository` (get by id, list, add, delete); one repository per
entity subclasses it and adds entity-specific lookups (e.g. `get_by_slug`,
`list_for_retailer`, `latest_for_retailer_product`). `PriceSnapshotRepository` deliberately has
no update method — Price Observations are immutable; corrections are new snapshots.
