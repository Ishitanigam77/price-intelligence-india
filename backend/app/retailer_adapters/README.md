# app/retailer_adapters/

Home of the common retailer adapter interface and one package per retailer. This is the
isolation boundary that lets the platform scale to 100+ retailers without changing core
comparison/matching/pricing logic. See `../../../RETAILER_ARCHITECTURE.md` for the full
contract and the legitimate-data-acquisition policy.

**Status**: empty scaffold. Introduced in **Phase 2 — Retailer Adapter Framework**. No
retailer-specific code — real or otherwise — exists here yet.
