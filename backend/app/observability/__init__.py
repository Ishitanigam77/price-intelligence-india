"""Cross-cutting observability primitives: structured logging, correlation IDs, metrics.

Nothing in this package knows about retailers, products, or prices — it is deliberately generic
so every layer (API, adapters, collectors, workers, ML) can share the same primitives.
Azure Monitor export is opt-in via `APPLICATIONINSIGHTS_CONNECTION_STRING`.
"""
