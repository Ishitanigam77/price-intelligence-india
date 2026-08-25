# app/domain/

Core business entities and rules, independent of any framework: Product, Product Variant,
Retailer Listing, Seller, Price Observation, and the invariants that govern them (e.g. variants
are never merged, observations are immutable).

This layer must not depend on `app/api/`, `app/db/`, or any specific retailer adapter.

**Status**: empty scaffold. Introduced in **Phase 1 — Core Domain Model & Database
Foundation**.
