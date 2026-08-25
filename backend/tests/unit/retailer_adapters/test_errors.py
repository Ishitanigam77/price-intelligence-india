"""Tests for adapter-level error types and their retailer-agnostic boundary."""

from app.retailer_adapters.base.errors import (
    DEFAULT_RETRYABLE_ERROR_CODES,
    AdapterDisabledError,
    AdapterErrorCode,
    AdapterTimeoutError,
    AdapterUnavailableError,
    InvalidRetailerResponseError,
    ProductNotFoundError,
    RateLimitExceededError,
    RetailerAdapterError,
    RetailerAlreadyRegisteredError,
    RetailerNotRegisteredError,
    TemporaryRetailerFailureError,
    UnexpectedAdapterFailureError,
    UnsupportedOperationError,
)


def test_every_adapter_error_is_a_retailer_adapter_error() -> None:
    subclasses = (
        AdapterUnavailableError,
        AdapterTimeoutError,
        RateLimitExceededError,
        TemporaryRetailerFailureError,
        ProductNotFoundError,
        UnsupportedOperationError,
        InvalidRetailerResponseError,
        AdapterDisabledError,
    )
    for cls in subclasses:
        error = cls("failure", retailer_id="scripted-store", operation="get_price")
        assert isinstance(error, RetailerAdapterError)
        assert error.retailer_id == "scripted-store"
        fields = error.log_fields()
        assert fields["retailer_id"] == "scripted-store"
        assert fields["error_type"] == error.code.value
        assert "payload" not in fields


def test_unexpected_failure_hides_the_vendor_exception_body() -> None:
    class VendorBoom(Exception):
        pass

    wrapped = UnexpectedAdapterFailureError.from_exception(
        VendorBoom("body containing api_key=super-secret"),
        retailer_id="scripted-store",
        operation="get_product",
    )
    assert wrapped.code is AdapterErrorCode.UNEXPECTED_ADAPTER_FAILURE
    assert "VendorBoom" in wrapped.message
    assert "super-secret" not in wrapped.message
    assert "api_key" not in wrapped.message


def test_default_retryable_set_matches_inherently_retryable_classes() -> None:
    retryable = {
        AdapterUnavailableError,
        AdapterTimeoutError,
        RateLimitExceededError,
        TemporaryRetailerFailureError,
    }
    permanent = {
        ProductNotFoundError,
        UnsupportedOperationError,
        InvalidRetailerResponseError,
        AdapterDisabledError,
    }
    for cls in retryable:
        assert cls.code in DEFAULT_RETRYABLE_ERROR_CODES
        assert cls.inherently_retryable is True
    for cls in permanent:
        assert cls.code not in DEFAULT_RETRYABLE_ERROR_CODES
        assert cls.inherently_retryable is False


def test_registry_errors_are_not_adapter_errors() -> None:
    missing = RetailerNotRegisteredError("unknown-store")
    duplicate = RetailerAlreadyRegisteredError("scripted-store")
    assert not isinstance(missing, RetailerAdapterError)
    assert not isinstance(duplicate, RetailerAdapterError)
    assert missing.retailer_id == "unknown-store"
