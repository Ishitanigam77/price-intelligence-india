# tests/unit/

Unit tests for domain logic and other pure/isolated components. Added alongside the real logic
they cover, starting in **Phase 1**.

`test_domain_validation.py` covers `app/domain/validation.py`: slug/currency/country-code
validation and product variant attribute normalization/`variant_key` derivation. No database or
web framework is involved — these run anywhere Python runs.
