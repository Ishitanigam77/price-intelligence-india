# app/core/

Shared, cross-cutting configuration and utilities: settings loading (from environment
variables / Azure Key Vault), shared exceptions, and other concerns used across layers.

**Status**: `config.py` implemented in **Phase 1** and extended in **Phase 2** with
framework-wide retailer adapter defaults (`RETAILER_ADAPTER_DEFAULT_*`,
`RETAILER_ADAPTERS_DISABLED`). A `pydantic-settings`-based `Settings` class reads from the
environment (see `.env.example`). No secrets are hardcoded. Per-retailer credentials are
added only alongside a real adapter, never speculatively.
