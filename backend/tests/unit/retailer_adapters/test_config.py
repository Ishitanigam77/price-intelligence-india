"""Tests for adapter configuration, environment overrides, and retry-policy arithmetic."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.domain.enums import SourceType
from app.retailer_adapters.base.config import (
    AdapterOperation,
    BackoffStrategy,
    RetryPolicy,
    apply_environment_overrides,
    build_adapter_config,
    env_prefix_for,
)
from app.retailer_adapters.base.errors import (
    AdapterErrorCode,
    AdapterMisconfiguredError,
    AdapterTimeoutError,
    ProductNotFoundError,
    RateLimitExceededError,
    TemporaryRetailerFailureError,
    UnsupportedOperationError,
)
from tests.unit.retailer_adapters.helpers import make_config


def test_env_prefix_uppercases_and_replaces_hyphens() -> None:
    assert env_prefix_for("mock-retailer-a") == "RETAILER_MOCK_RETAILER_A_"


class TestRetryPolicy:
    def test_exponential_backoff_grows_then_caps(self) -> None:
        policy = RetryPolicy(
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            initial_backoff_seconds=0.5,
            backoff_multiplier=2.0,
            max_backoff_seconds=2.0,
            jitter_ratio=0.0,
        )
        assert policy.backoff_seconds(attempt=1) == 0.5
        assert policy.backoff_seconds(attempt=2) == 1.0
        assert policy.backoff_seconds(attempt=3) == 2.0
        assert policy.backoff_seconds(attempt=4) == 2.0

    def test_linear_and_fixed_strategies(self) -> None:
        linear = RetryPolicy(
            backoff_strategy=BackoffStrategy.LINEAR,
            initial_backoff_seconds=1.0,
            max_backoff_seconds=10.0,
            jitter_ratio=0.0,
        )
        fixed = RetryPolicy(
            backoff_strategy=BackoffStrategy.FIXED,
            initial_backoff_seconds=0.25,
            max_backoff_seconds=10.0,
            jitter_ratio=0.0,
        )
        assert linear.backoff_seconds(attempt=1) == 1.0
        assert linear.backoff_seconds(attempt=3) == 3.0
        assert fixed.backoff_seconds(attempt=1) == 0.25
        assert fixed.backoff_seconds(attempt=8) == 0.25

    def test_jitter_is_a_pure_function_of_the_supplied_fraction(self) -> None:
        policy = RetryPolicy(initial_backoff_seconds=1.0, jitter_ratio=0.5, max_backoff_seconds=10)
        assert policy.backoff_seconds(attempt=1, jitter_fraction=0.0) == 1.0
        assert policy.backoff_seconds(attempt=1, jitter_fraction=1.0) == 1.5

    def test_retry_after_from_the_retailer_is_honoured_but_capped(self) -> None:
        policy = RetryPolicy(initial_backoff_seconds=0.5, max_backoff_seconds=4.0, jitter_ratio=0.0)
        error = RateLimitExceededError(
            "throttled", retailer_id="scripted-store", retry_after_seconds=3.0
        )
        assert policy.delay_for(error, attempt=1) == 3.0
        over_cap = RateLimitExceededError(
            "throttled", retailer_id="scripted-store", retry_after_seconds=30.0
        )
        assert policy.delay_for(over_cap, attempt=1) == 4.0

    @pytest.mark.parametrize(
        "error_cls",
        [AdapterTimeoutError, TemporaryRetailerFailureError, RateLimitExceededError],
    )
    def test_transient_errors_are_retryable_by_default(self, error_cls: type) -> None:
        error = error_cls("transient", retailer_id="scripted-store")
        assert RetryPolicy().is_retryable(error) is True

    @pytest.mark.parametrize(
        "error_cls",
        [ProductNotFoundError, UnsupportedOperationError],
    )
    def test_permanent_errors_are_not_retried(self, error_cls: type) -> None:
        error = error_cls("permanent", retailer_id="scripted-store")
        assert RetryPolicy().is_retryable(error) is False

    def test_retryable_set_can_be_narrowed(self) -> None:
        policy = RetryPolicy(retryable_error_codes=frozenset({AdapterErrorCode.TIMEOUT}))
        assert policy.is_retryable(AdapterTimeoutError("t", retailer_id="scripted-store")) is True
        assert (
            policy.is_retryable(TemporaryRetailerFailureError("x", retailer_id="scripted-store"))
            is False
        )


class TestRetailerAdapterConfig:
    def test_health_check_is_always_supported(self) -> None:
        config = make_config(supported_operations=frozenset({AdapterOperation.GET_PRICE}))
        assert config.supports(AdapterOperation.HEALTH_CHECK) is True
        assert config.supports(AdapterOperation.GET_PRICE) is True
        assert config.supports(AdapterOperation.SEARCH_PRODUCTS) is False

    def test_rejects_empty_operations(self) -> None:
        with pytest.raises(ValidationError):
            make_config(supported_operations=frozenset())

    def test_rejects_declaring_health_check(self) -> None:
        with pytest.raises(ValidationError):
            make_config(supported_operations=frozenset({AdapterOperation.HEALTH_CHECK}))

    def test_rejects_credential_looking_options(self) -> None:
        with pytest.raises(ValidationError, match="must not carry credentials"):
            make_config(options={"api_key": "should-never-be-here"})

    def test_attempt_timeout_prefers_retry_policy_override(self) -> None:
        config = make_config(timeout_seconds=10.0, retry_policy=RetryPolicy(timeout_seconds=2.5))
        assert config.attempt_timeout_seconds == 2.5


class TestEnvironmentOverrides:
    def test_per_retailer_overrides_apply_independently(self) -> None:
        config_a = make_config(retailer_id="mock-retailer-a", timeout_seconds=10.0)
        config_b = make_config(retailer_id="mock-retailer-b", timeout_seconds=10.0)
        env = {
            "RETAILER_MOCK_RETAILER_A_TIMEOUT_SECONDS": "2.5",
            "RETAILER_MOCK_RETAILER_A_MAX_ATTEMPTS": "5",
            "RETAILER_MOCK_RETAILER_A_REQUESTS_PER_MINUTE": "12",
            "RETAILER_MOCK_RETAILER_B_ENABLED": "false",
        }
        settings = Settings(retailer_adapters_disabled="")
        updated_a = apply_environment_overrides(config_a, env=env, settings=settings)
        updated_b = apply_environment_overrides(config_b, env=env, settings=settings)
        assert updated_a.timeout_seconds == 2.5
        assert updated_a.retry_policy.max_attempts == 5
        assert updated_a.rate_limit.max_requests_per_minute == 12
        assert updated_a.enabled is True
        assert updated_b.enabled is False
        assert updated_b.timeout_seconds == 10.0

    def test_global_disable_list_wins_over_per_retailer_enabled(self) -> None:
        config = make_config(retailer_id="mock-retailer-a", enabled=True)
        updated = apply_environment_overrides(
            config,
            env={"RETAILER_MOCK_RETAILER_A_ENABLED": "true"},
            settings=Settings(retailer_adapters_disabled="mock-retailer-a, mock-retailer-c"),
        )
        assert updated.enabled is False

    def test_invalid_override_is_a_framework_error(self) -> None:
        config = make_config(retailer_id="mock-retailer-a")
        with pytest.raises(AdapterMisconfiguredError) as exc:
            apply_environment_overrides(
                config,
                env={"RETAILER_MOCK_RETAILER_A_TIMEOUT_SECONDS": "-1"},
                settings=Settings(),
            )
        assert exc.value.retailer_id == "mock-retailer-a"
        assert exc.value.code is AdapterErrorCode.ADAPTER_MISCONFIGURED

    def test_build_adapter_config_uses_settings_defaults(self) -> None:
        settings = Settings(
            retailer_adapter_default_timeout_seconds=7.0,
            retailer_adapter_default_max_attempts=4,
            retailer_adapter_default_requests_per_minute=15,
        )
        config = build_adapter_config(
            retailer_id="example-store",
            retailer_name="Example Store",
            source_type=SourceType.PRODUCT_FEED,
            supported_categories=("audio",),
            supported_operations=frozenset({AdapterOperation.GET_PRICE}),
            settings=settings,
            env={},
        )
        assert config.timeout_seconds == 7.0
        assert config.retry_policy.max_attempts == 4
        assert config.rate_limit.max_requests_per_minute == 15
        assert config.source_type is SourceType.PRODUCT_FEED
