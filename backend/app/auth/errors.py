"""Authentication-layer errors.

These are raised by token verification and the current-user dependency. HTTP status mapping
lives in `app.api.errors` so route handlers stay free of status-code concerns.
"""


class AuthenticationError(Exception):
    """The request is missing a valid authenticated identity (HTTP 401)."""

    def __init__(self, message: str = "Authentication required.") -> None:
        super().__init__(message)
        self.message = message


class AuthorizationError(Exception):
    """The authenticated user is not allowed to access the requested resource (HTTP 403)."""

    def __init__(self, message: str = "You are not allowed to access this resource.") -> None:
        super().__init__(message)
        self.message = message
