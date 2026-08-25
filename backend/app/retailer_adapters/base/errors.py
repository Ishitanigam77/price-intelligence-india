"""The framework's error taxonomy.

Two rules make this taxonomy the error boundary between retailers and the core application:

1. **Every failure crossing the adapter boundary is a `RetailerAdapterError`.** Retailer-native
   exceptions (HTTP client errors, parse errors, feed library exceptions) are caught inside the
   adapter/executor and translated into one of the classes below. Core code therefore never has
   to know, or catch, a retailer-specific exception type.
2. **Messages stay retailer-agnostic.** A raiser supplies a short, stable description of *what
   kind* of failure occurred — never a raw retailer payload, request URL with credentials, or
   vendor error blob. Full detail belongs in the structured log record (which is redacted), not
   in an exception that propagates into the domain.

Each error carries a stable `code` so callers (and the retry policy) can branch on the failure
*kind* without string matching, and so metrics/logs can be aggregated by failure type.
"""

from enum import StrEnum
from typing import Any, ClassVar


class AdapterErrorCode(StrEnum):
    """Stable, retailer-agnostic classification of an adapter failure."""

    ADAPTER_UNAVAILABLE = "adapter_unavailable"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    PRODUCT_NOT_FOUND = "product_not_found"
    UNSUPPORTED_OPERATION = "unsupported_operation"
    INVALID_RETAILER_RESPONSE = "invalid_retailer_response"
    TEMPORARY_RETAILER_FAILURE = "temporary_retailer_failure"
    ADAPTER_DISABLED = "adapter_disabled"
    ADAPTER_MISCONFIGURED = "adapter_misconfigured"
    UNEXPECTED_ADAPTER_FAILURE = "unexpected_adapter_failure"


class RetailerAdapterError(Exception):
    """Base class for every failure surfaced by a retailer adapter."""

    code: ClassVar[AdapterErrorCode]
    #: Whether this failure kind is *inherently* worth retrying. The effective decision is made
    #: by `RetryPolicy.is_retryable`, which is configuration-driven and may narrow this.
    inherently_retryable: ClassVar[bool] = False

    def __init__(
        self,
        message: str,
        *,
        retailer_id: str,
        operation: str | None = None,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.retailer_id = retailer_id
        self.operation = operation
        self.retry_after_seconds = retry_after_seconds

    def log_fields(self) -> dict[str, Any]:
        """Structured fields describing this error, safe to log."""
        fields: dict[str, Any] = {
            "retailer_id": self.retailer_id,
            "error_type": self.code.value,
            "error_message": self.message,
        }
        if self.operation is not None:
            fields["operation"] = self.operation
        if self.retry_after_seconds is not None:
            fields["retry_after_seconds"] = self.retry_after_seconds
        return fields

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(code={self.code.value!r}, retailer_id={self.retailer_id!r}, "
            f"operation={self.operation!r})"
        )


class AdapterUnavailableError(RetailerAdapterError):
    """The retailer's legitimate source could not be reached at all (connection failure)."""

    code = AdapterErrorCode.ADAPTER_UNAVAILABLE
    inherently_retryable = True


class AdapterTimeoutError(RetailerAdapterError):
    """The operation exceeded its configured timeout and was abandoned."""

    code = AdapterErrorCode.TIMEOUT
    inherently_retryable = True


class RateLimitExceededError(RetailerAdapterError):
    """The retailer's published rate limit was reached.

    Raised when the source signals throttling. The framework's own limiter paces requests to
    stay *within* the published limit — it never attempts to evade or exceed one.
    """

    code = AdapterErrorCode.RATE_LIMITED
    inherently_retryable = True


class TemporaryRetailerFailureError(RetailerAdapterError):
    """The source responded with a transient failure (e.g. a 5xx) that may succeed if retried."""

    code = AdapterErrorCode.TEMPORARY_RETAILER_FAILURE
    inherently_retryable = True


class ProductNotFoundError(RetailerAdapterError):
    """The requested listing does not exist at this retailer. Retrying cannot change that."""

    code = AdapterErrorCode.PRODUCT_NOT_FOUND


class UnsupportedOperationError(RetailerAdapterError):
    """The adapter does not implement/declare support for the requested operation."""

    code = AdapterErrorCode.UNSUPPORTED_OPERATION


class InvalidRetailerResponseError(RetailerAdapterError):
    """The source responded, but the payload could not be mapped to the standardized models.

    Deliberately *not* retryable: a malformed or contract-breaking response is a data problem,
    and hammering the retailer will not fix it. The raiser must describe the shape problem
    without echoing the payload.
    """

    code = AdapterErrorCode.INVALID_RETAILER_RESPONSE


class AdapterDisabledError(RetailerAdapterError):
    """The adapter is registered but currently disabled, so the operation was not attempted."""

    code = AdapterErrorCode.ADAPTER_DISABLED


class AdapterMisconfiguredError(RetailerAdapterError):
    """The adapter's configuration is invalid or incomplete (e.g. a required setting is absent)."""

    code = AdapterErrorCode.ADAPTER_MISCONFIGURED


class UnexpectedAdapterFailureError(RetailerAdapterError):
    """An exception escaped an adapter without being translated into a framework error.

    The framework converts it here so nothing retailer-specific reaches the core domain. Only
    the offending exception's *type name* is carried in the message; the full traceback is
    logged instead of being propagated.
    """

    code = AdapterErrorCode.UNEXPECTED_ADAPTER_FAILURE

    @classmethod
    def from_exception(
        cls, exc: BaseException, *, retailer_id: str, operation: str | None = None
    ) -> "UnexpectedAdapterFailureError":
        return cls(
            f"Adapter raised an untranslated {type(exc).__name__}.",
            retailer_id=retailer_id,
            operation=operation,
        )


#: Failure kinds retried by default. Everything else is a permanent condition for the current
#: input (not found, unsupported, malformed response, misconfiguration) where retrying only adds
#: load on the retailer without changing the outcome.
DEFAULT_RETRYABLE_ERROR_CODES: frozenset[AdapterErrorCode] = frozenset(
    {
        AdapterErrorCode.ADAPTER_UNAVAILABLE,
        AdapterErrorCode.TIMEOUT,
        AdapterErrorCode.RATE_LIMITED,
        AdapterErrorCode.TEMPORARY_RETAILER_FAILURE,
    }
)


class RetailerRegistryError(Exception):
    """Base class for registry-level (wiring) problems, distinct from adapter call failures."""


class RetailerNotRegisteredError(RetailerRegistryError, KeyError):
    """No adapter is registered for the requested retailer ID."""

    def __init__(self, retailer_id: str) -> None:
        super().__init__(f"No retailer adapter is registered for retailer_id={retailer_id!r}.")
        self.retailer_id = retailer_id


class RetailerAlreadyRegisteredError(RetailerRegistryError):
    """An adapter is already registered for that retailer ID."""

    def __init__(self, retailer_id: str) -> None:
        super().__init__(
            f"A retailer adapter is already registered for retailer_id={retailer_id!r}. "
            "Pass replace=True to intentionally swap it."
        )
        self.retailer_id = retailer_id


class AdapterContractError(RetailerRegistryError):
    """An adapter declares support for an operation it does not implement (or vice versa).

    Raised at construction time so a broken adapter fails fast at wiring time rather than in
    production on the first call.
    """
