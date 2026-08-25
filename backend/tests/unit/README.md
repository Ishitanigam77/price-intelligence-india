# tests/unit/

Unit tests for domain logic and other pure/isolated components. Added alongside the real logic
they cover, starting in **Phase 1**.

- `test_domain_validation.py` covers `app/domain/validation.py`: slug/currency/country-code
  validation and product variant attribute normalization/`variant_key` derivation.
- `test_config.py` (FastAPI backend application foundation) covers `app.core.config.Settings`:
  defaults, `log_level` validation, and `cors_allowed_origins_list` parsing.
- `observability/` — JSON logging, correlation IDs, metrics sink.
- `retailer_adapters/` — adapter contract, registry, config, timeout/retry, rate limits,
  mock retailers, normalization, extensibility, and core-domain isolation.

No database or web framework is involved — these run anywhere Python runs.
