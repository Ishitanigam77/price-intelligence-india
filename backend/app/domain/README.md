# app/domain/

Core business entities and rules, independent of any framework: Product, Product Variant,
Retailer Listing, Seller, Price Observation, and the invariants that govern them (e.g. variants
are never merged, observations are immutable).

This layer must not depend on `app/api/`, `app/db/`, or any specific retailer adapter.

**Status**: implemented in **Phase 1 — Core Domain Model & Database Foundation**.

- `enums.py` — `AvailabilityStatus`, `SourceType`, `ConfidenceLevel`, `ProductIdentifierType`,
  `SaleEventType`, `SaleEventSource`, `SaleEventStatus`, `CollectionJobType`,
  `CollectionJobStatus`, `CollectionErrorCategory`.
- `exceptions.py` — domain validation errors (e.g. `InvalidSlugError`, `NegativeAmountError`,
  `InvalidSaleEventError`).
- `validation.py` — pure functions: slug/currency/country-code validation, variant attribute
  normalization, the deterministic `variant_key` derivation used to prevent duplicate
  logical product variants, and sale-event window/scope/source provenance checks.

These are consumed by the ORM models in `app/db/models/` (via `@validates` hooks) so invalid
data is rejected before it reaches the database, in addition to the database's own CHECK
constraints.
