"""Domain-level validation errors.

Raised by domain validators and by ORM `@validates` hooks so that invalid data is rejected with
a clear, specific error before it ever reaches the database (defense in depth alongside DB-level
CHECK constraints).
"""


class DomainError(ValueError):
    """Base class for all domain validation errors."""


class InvalidSlugError(DomainError):
    """A slug does not match the required lowercase-kebab-case format."""


class InvalidCurrencyCodeError(DomainError):
    """A currency code is not a well-formed 3-letter ISO 4217 code."""


class InvalidCountryCodeError(DomainError):
    """A country code is not a well-formed 2-letter ISO 3166-1 alpha-2 code."""


class InvalidVariantAttributesError(DomainError):
    """A product variant's attribute set is empty or malformed."""


class NegativeAmountError(DomainError):
    """A monetary amount (price, fee, MRP) was negative."""
