"""Adapter configuration: capabilities, timeouts, retry policy, and rate limits.

Configuration is *data*, not code: an adapter receives a `RetailerAdapterConfig` and the
framework derives all of its timeout/retry/rate-limit/enablement behaviour from it. That is what
makes every adapter independently tunable without a single line of retailer-specific framework
code.

Values resolve in three layers, most specific last:

1. the adapter's own declared defaults (capabilities, source type, categories),
2. framework-wide defaults from application settings (`app.core.config.Settings`, env-driven),
3. per-retailer environment overrides, e.g. `RETAILER_EXAMPLE_STORE_TIMEOUT_SECONDS`.

Credentials are deliberately absent from this model. Per-retailer secrets are read from the
environment (Azure Key Vault in deployed environments) by the adapter that needs them, when
that adapter is introduced — never stored in, or logged through, a config object. `options`
rejects credential-looking keys for exactly this reason.
"""

import os
from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.core.config import Settings, get_settings
from app.domain.enums import SourceType
from app.domain.validation import validate_slug
from app.observability.logging import looks_sensitive
from app.retailer_adapters.base.errors import (
    DEFAULT_RETRYABLE_ERROR_CODES,
    AdapterErrorCode,
    AdapterMisconfiguredError,
    RetailerAdapterError,
)


class AdapterOperation(StrEnum):
    """The operations of the adapter contract, used for capability declaration and tagging."""

    SEARCH_PRODUCTS = "search_products"
    GET_PRODUCT = "get_product"
    GET_PRICE = "get_price"
    GET_AVAILABILITY = "get_availability"
    GET_PRODUCT_IDENTIFIERS = "get_product_identifiers"
    HEALTH_CHECK = "health_check"


#: Operations an adapter may choose whether or not to support. `HEALTH_CHECK` is excluded
#: because every adapter must be health-checkable, so declaring it would be meaningless.
DECLARABLE_OPERATIONS: frozenset[AdapterOperation] = frozenset(AdapterOperation) - {
    AdapterOperation.HEALTH_CHECK
}


class BackoffStrategy(StrEnum):
    """How the delay between retry attempts grows."""

    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"


class RetryPolicy(BaseModel):
    """When and how a failed adapter attempt is retried.

    Retries only ever apply to failure kinds listed in `retryable_error_codes`. A "not found",
    "unsupported operation", "invalid response", or "misconfigured" outcome is permanent for the
    given input, so retrying it would add load on the retailer for no possible benefit.
    """

    model_config = ConfigDict(frozen=True)

    max_attempts: int = Field(default=3, ge=1, le=10)
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    initial_backoff_seconds: float = Field(default=0.5, ge=0.0)
    max_backoff_seconds: float = Field(default=10.0, ge=0.0)
    backoff_multiplier: float = Field(default=2.0, ge=1.0)
    #: Fraction of the computed delay that may be added as random jitter, to avoid many workers
    #: retrying against the same retailer in lockstep. `0.0` makes delays fully deterministic.
    jitter_ratio: float = Field(default=0.1, ge=0.0, le=1.0)
    retryable_error_codes: frozenset[AdapterErrorCode] = DEFAULT_RETRYABLE_ERROR_CODES
    #: Per-attempt timeout override. When unset, `RetailerAdapterConfig.timeout_seconds` applies.
    timeout_seconds: float | None = Field(default=None, gt=0.0)

    def is_retryable(self, error: RetailerAdapterError) -> bool:
        """Whether `error` should be retried under this policy."""
        return error.code in self.retryable_error_codes

    def backoff_seconds(self, *, attempt: int, jitter_fraction: float = 0.0) -> float:
        """Delay before the attempt following `attempt` (1-based, the attempt that just failed).

        `jitter_fraction` is supplied by the caller (a `[0.0, 1.0)` sample) so the delay stays a
        pure function and is exactly reproducible in tests.
        """
        if attempt < 1:
            raise ValueError("attempt must be >= 1")
        base = self.initial_backoff_seconds
        if self.backoff_strategy is BackoffStrategy.LINEAR:
            base = self.initial_backoff_seconds * attempt
        elif self.backoff_strategy is BackoffStrategy.EXPONENTIAL:
            base = self.initial_backoff_seconds * (self.backoff_multiplier ** (attempt - 1))
        capped = min(base, self.max_backoff_seconds)
        return capped + capped * self.jitter_ratio * jitter_fraction

    def delay_for(
        self, error: RetailerAdapterError, *, attempt: int, jitter_fraction: float = 0.0
    ) -> float:
        """Delay to wait after `error`, honouring a retailer-signalled `retry_after_seconds`.

        When a retailer tells us how long to wait, that instruction wins over our own backoff
        curve (capped by `max_backoff_seconds`) — respecting a published limit rather than
        retrying sooner than we were asked to.
        """
        computed = self.backoff_seconds(attempt=attempt, jitter_fraction=jitter_fraction)
        if error.retry_after_seconds is not None:
            return min(max(error.retry_after_seconds, computed), self.max_backoff_seconds)
        return computed


class RateLimitConfig(BaseModel):
    """Per-retailer pacing settings.

    This exists to keep the platform *inside* whatever limit a retailer publishes — it is a
    politeness/compliance mechanism, never a means of evading a limit. Defaults are deliberately
    conservative; a retailer's documented allowance is configured explicitly per adapter.
    """

    model_config = ConfigDict(frozen=True)

    max_requests_per_minute: int = Field(default=60, ge=1)
    #: How many requests may be issued back-to-back before pacing kicks in. `1` means strictly
    #: evenly spaced requests.
    burst_size: int = Field(default=1, ge=1)
    #: Upper bound on in-flight requests to this retailer.
    max_concurrent_requests: int = Field(default=1, ge=1)

    @property
    def min_interval_seconds(self) -> float:
        """Average spacing between requests implied by `max_requests_per_minute`."""
        return 60.0 / self.max_requests_per_minute


class RetailerAdapterConfig(BaseModel):
    """Identity, capabilities, and operational policy for a single retailer adapter."""

    model_config = ConfigDict(frozen=True)

    retailer_id: str
    retailer_name: str = Field(min_length=1, max_length=200)
    #: The lawful access method this adapter uses; becomes `source_type` on every observation.
    source_type: SourceType
    #: Category slugs this adapter can serve, e.g. `("mobiles", "audio")`.
    supported_categories: tuple[str, ...] = Field(min_length=1)
    supported_operations: frozenset[AdapterOperation]
    enabled: bool = True
    timeout_seconds: float = Field(default=10.0, gt=0.0)
    retry_policy: RetryPolicy = RetryPolicy()
    rate_limit: RateLimitConfig = RateLimitConfig()
    #: Non-secret, adapter-specific settings (endpoints, page sizes, feed names, ...).
    options: Mapping[str, str] = Field(default_factory=dict)

    @field_validator("retailer_id")
    @classmethod
    def _validate_retailer_id(cls, value: str) -> str:
        return validate_slug(value)

    @field_validator("supported_categories")
    @classmethod
    def _validate_categories(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for category in value:
            validate_slug(category)
        return value

    @field_validator("supported_operations")
    @classmethod
    def _validate_operations(
        cls, value: frozenset[AdapterOperation]
    ) -> frozenset[AdapterOperation]:
        if not value:
            raise ValueError("An adapter must support at least one operation.")
        undeclarable = value - DECLARABLE_OPERATIONS
        if undeclarable:
            names = ", ".join(sorted(operation.value for operation in undeclarable))
            raise ValueError(
                f"{names} cannot be declared in supported_operations: every adapter must "
                "support it unconditionally."
            )
        return value

    @field_validator("options")
    @classmethod
    def _reject_credential_options(cls, value: Mapping[str, str]) -> Mapping[str, str]:
        offenders = sorted(key for key in value if looks_sensitive(str(key)))
        if offenders:
            raise ValueError(
                f"options must not carry credentials (offending keys: {', '.join(offenders)}). "
                "Read secrets from the environment/Key Vault inside the adapter instead."
            )
        return value

    def supports(self, operation: AdapterOperation) -> bool:
        """Whether this adapter declares support for `operation`."""
        return operation is AdapterOperation.HEALTH_CHECK or operation in self.supported_operations

    def serves_category(self, category: str) -> bool:
        """Whether this adapter covers the given category slug."""
        return category in self.supported_categories

    @property
    def attempt_timeout_seconds(self) -> float:
        """Timeout applied to a single attempt (retry-policy override wins when set)."""
        return self.retry_policy.timeout_seconds or self.timeout_seconds


def _parse_bool(raw: str, *, variable: str, retailer_id: str) -> bool:
    lowered = raw.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    raise AdapterMisconfiguredError(
        f"{variable} must be a boolean-like value.", retailer_id=retailer_id
    )


def _parse_number(raw: str, *, variable: str, retailer_id: str, cast: type) -> Any:
    try:
        return cast(raw.strip())
    except ValueError as exc:
        raise AdapterMisconfiguredError(
            f"{variable} must be a valid {cast.__name__}.", retailer_id=retailer_id
        ) from exc


def env_prefix_for(retailer_id: str) -> str:
    """Environment variable prefix for a retailer's overrides (e.g. `RETAILER_BIG_MART_`)."""
    return f"RETAILER_{retailer_id.upper().replace('-', '_')}_"


def apply_environment_overrides(
    config: RetailerAdapterConfig,
    *,
    env: Mapping[str, str] | None = None,
    settings: Settings | None = None,
) -> RetailerAdapterConfig:
    """Return `config` with per-retailer environment overrides and the global disable list applied.

    Recognised variables (all optional), where `<ID>` is the retailer ID upper-cased with
    hyphens replaced by underscores:

    - `RETAILER_<ID>_ENABLED`
    - `RETAILER_<ID>_TIMEOUT_SECONDS`
    - `RETAILER_<ID>_MAX_ATTEMPTS`
    - `RETAILER_<ID>_REQUESTS_PER_MINUTE`
    - `RETAILER_<ID>_MAX_CONCURRENT_REQUESTS`

    A retailer named in `RETAILER_ADAPTERS_DISABLED` is disabled regardless of its own
    `RETAILER_<ID>_ENABLED` value, so operations can switch a retailer off globally in one place.
    """
    environ = os.environ if env is None else env
    resolved_settings = settings if settings is not None else get_settings()
    prefix = env_prefix_for(config.retailer_id)
    updates: dict[str, Any] = {}

    enabled_raw = environ.get(f"{prefix}ENABLED")
    if enabled_raw is not None:
        updates["enabled"] = _parse_bool(
            enabled_raw, variable=f"{prefix}ENABLED", retailer_id=config.retailer_id
        )
    if config.retailer_id in resolved_settings.disabled_retailer_ids:
        updates["enabled"] = False

    timeout_raw = environ.get(f"{prefix}TIMEOUT_SECONDS")
    if timeout_raw is not None:
        updates["timeout_seconds"] = _parse_number(
            timeout_raw,
            variable=f"{prefix}TIMEOUT_SECONDS",
            retailer_id=config.retailer_id,
            cast=float,
        )

    attempts_raw = environ.get(f"{prefix}MAX_ATTEMPTS")
    rate_limit_updates: dict[str, Any] = {}
    rpm_raw = environ.get(f"{prefix}REQUESTS_PER_MINUTE")
    concurrency_raw = environ.get(f"{prefix}MAX_CONCURRENT_REQUESTS")

    try:
        if attempts_raw is not None:
            max_attempts = _parse_number(
                attempts_raw,
                variable=f"{prefix}MAX_ATTEMPTS",
                retailer_id=config.retailer_id,
                cast=int,
            )
            updates["retry_policy"] = config.retry_policy.model_copy(
                update={"max_attempts": max_attempts}
            )

        if rpm_raw is not None:
            rate_limit_updates["max_requests_per_minute"] = _parse_number(
                rpm_raw,
                variable=f"{prefix}REQUESTS_PER_MINUTE",
                retailer_id=config.retailer_id,
                cast=int,
            )
        if concurrency_raw is not None:
            rate_limit_updates["max_concurrent_requests"] = _parse_number(
                concurrency_raw,
                variable=f"{prefix}MAX_CONCURRENT_REQUESTS",
                retailer_id=config.retailer_id,
                cast=int,
            )
        if rate_limit_updates:
            updates["rate_limit"] = config.rate_limit.model_copy(update=rate_limit_updates)

        if not updates:
            return config
        # Re-validated rather than `model_copy`-ed so an out-of-range override (e.g. a negative
        # timeout) is rejected here instead of silently producing an invalid config.
        return RetailerAdapterConfig.model_validate({**config.model_dump(), **updates})
    except (ValueError, ValidationError) as exc:
        raise AdapterMisconfiguredError(
            f"Environment overrides produced an invalid configuration: {exc}",
            retailer_id=config.retailer_id,
        ) from exc


def build_adapter_config(
    *,
    retailer_id: str,
    retailer_name: str,
    source_type: SourceType,
    supported_categories: tuple[str, ...],
    supported_operations: frozenset[AdapterOperation],
    options: Mapping[str, str] | None = None,
    enabled: bool | None = None,
    timeout_seconds: float | None = None,
    retry_policy: RetryPolicy | None = None,
    rate_limit: RateLimitConfig | None = None,
    settings: Settings | None = None,
    env: Mapping[str, str] | None = None,
) -> RetailerAdapterConfig:
    """Build an adapter config from its declared identity plus settings/environment defaults.

    This is the entry point adapter packages use in their `config.py`, so every adapter picks up
    the same framework-wide defaults (and the same override mechanism) without restating them.
    """
    resolved_settings = settings if settings is not None else get_settings()
    resolved_retry = retry_policy or RetryPolicy(
        max_attempts=resolved_settings.retailer_adapter_default_max_attempts
    )
    resolved_rate_limit = rate_limit or RateLimitConfig(
        max_requests_per_minute=resolved_settings.retailer_adapter_default_requests_per_minute,
        max_concurrent_requests=(
            resolved_settings.retailer_adapter_default_max_concurrent_requests
        ),
    )
    config = RetailerAdapterConfig(
        retailer_id=retailer_id,
        retailer_name=retailer_name,
        source_type=source_type,
        supported_categories=supported_categories,
        supported_operations=supported_operations,
        enabled=True if enabled is None else enabled,
        timeout_seconds=(
            resolved_settings.retailer_adapter_default_timeout_seconds
            if timeout_seconds is None
            else timeout_seconds
        ),
        retry_policy=resolved_retry,
        rate_limit=resolved_rate_limit,
        options=dict(options or {}),
    )
    return apply_environment_overrides(config, env=env, settings=resolved_settings)
