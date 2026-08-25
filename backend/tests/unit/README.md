# tests/unit/

Unit tests for domain logic and other pure/isolated components. Added alongside the real logic
they cover, starting in **Phase 1**.

- `test_domain_validation.py` — `app/domain/validation.py` (no database).
- `observability/` — JSON logging, correlation IDs, metrics sink.
- `retailer_adapters/` — adapter contract, registry, config, timeout/retry, rate limits,
  mock retailers, normalization, extensibility, and core-domain isolation.

