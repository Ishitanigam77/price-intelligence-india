"""Map adapter failures onto collection failures without leaking retailer-native exceptions."""

from __future__ import annotations

from app.collectors.errors import CollectionFailure
from app.domain.enums import CollectionErrorCategory
from app.retailer_adapters.base.errors import AdapterErrorCode, RetailerAdapterError

_RETRYABLE_ADAPTER_CODES: frozenset[AdapterErrorCode] = frozenset(
    {
        AdapterErrorCode.ADAPTER_UNAVAILABLE,
        AdapterErrorCode.TIMEOUT,
        AdapterErrorCode.RATE_LIMITED,
        AdapterErrorCode.TEMPORARY_RETAILER_FAILURE,
    }
)

_CATEGORY_BY_CODE: dict[AdapterErrorCode, CollectionErrorCategory] = {
    AdapterErrorCode.TIMEOUT: CollectionErrorCategory.TIMEOUT,
    AdapterErrorCode.RATE_LIMITED: CollectionErrorCategory.RATE_LIMITED,
    AdapterErrorCode.ADAPTER_UNAVAILABLE: CollectionErrorCategory.TEMPORARY_FAILURE,
    AdapterErrorCode.TEMPORARY_RETAILER_FAILURE: CollectionErrorCategory.TEMPORARY_FAILURE,
    AdapterErrorCode.INVALID_RETAILER_RESPONSE: CollectionErrorCategory.VALIDATION,
    AdapterErrorCode.PRODUCT_NOT_FOUND: CollectionErrorCategory.PERMANENT,
    AdapterErrorCode.UNSUPPORTED_OPERATION: CollectionErrorCategory.PERMANENT,
    AdapterErrorCode.ADAPTER_DISABLED: CollectionErrorCategory.PERMANENT,
    AdapterErrorCode.ADAPTER_MISCONFIGURED: CollectionErrorCategory.CONFIGURATION,
    AdapterErrorCode.UNEXPECTED_ADAPTER_FAILURE: CollectionErrorCategory.UNEXPECTED,
}


def collection_failure_from_adapter(
    error: RetailerAdapterError,
    *,
    operation_target: str | None = None,
) -> CollectionFailure:
    category = _CATEGORY_BY_CODE.get(error.code, CollectionErrorCategory.UNEXPECTED)
    retryable = error.code in _RETRYABLE_ADAPTER_CODES
    return CollectionFailure(
        error.message,
        category=category,
        retailer_id=error.retailer_id,
        retryable=retryable,
        operation=error.operation,
        operation_target=operation_target,
    )


def collection_failure_from_exception(
    exc: BaseException,
    *,
    retailer_id: str,
    operation: str,
    operation_target: str | None = None,
) -> CollectionFailure:
    if isinstance(exc, CollectionFailure):
        return exc
    if isinstance(exc, RetailerAdapterError):
        return collection_failure_from_adapter(exc, operation_target=operation_target)
    return CollectionFailure(
        f"Collection raised {type(exc).__name__}.",
        category=CollectionErrorCategory.UNEXPECTED,
        retailer_id=retailer_id,
        retryable=False,
        operation=operation,
        operation_target=operation_target,
    )
