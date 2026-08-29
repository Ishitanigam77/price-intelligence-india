"""Collection-layer errors, distinct from adapter-boundary `RetailerAdapterError`s."""

from __future__ import annotations

from app.domain.enums import CollectionErrorCategory


class CollectionFailure(Exception):
    """A failure during collection orchestration for one retailer/operation."""

    def __init__(
        self,
        message: str,
        *,
        category: CollectionErrorCategory,
        retailer_id: str,
        retryable: bool,
        operation: str | None = None,
        operation_target: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.category = category
        self.retailer_id = retailer_id
        self.retryable = retryable
        self.operation = operation
        self.operation_target = operation_target


class CollectionTimeoutError(CollectionFailure):
    def __init__(
        self,
        message: str,
        *,
        retailer_id: str,
        operation: str | None = None,
        operation_target: str | None = None,
    ) -> None:
        super().__init__(
            message,
            category=CollectionErrorCategory.TIMEOUT,
            retailer_id=retailer_id,
            retryable=True,
            operation=operation,
            operation_target=operation_target,
        )


class CollectionConfigurationError(CollectionFailure):
    def __init__(self, message: str, *, retailer_id: str = "configuration") -> None:
        super().__init__(
            message,
            category=CollectionErrorCategory.CONFIGURATION,
            retailer_id=retailer_id,
            retryable=False,
            operation="configure",
        )


class CollectionPermanentError(CollectionFailure):
    def __init__(
        self,
        message: str,
        *,
        retailer_id: str,
        category: CollectionErrorCategory = CollectionErrorCategory.PERMANENT,
        operation: str | None = None,
        operation_target: str | None = None,
    ) -> None:
        super().__init__(
            message,
            category=category,
            retailer_id=retailer_id,
            retryable=False,
            operation=operation,
            operation_target=operation_target,
        )
