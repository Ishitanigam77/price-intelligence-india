"""Cross-cutting observability primitives: structured logging, correlation IDs, metrics.

Nothing in this package knows about retailers, products, or prices — it is deliberately generic
so every layer (API, adapters, future collectors/workers) can share the same primitives.
"""
