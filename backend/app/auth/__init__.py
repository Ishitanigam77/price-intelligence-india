"""Clerk authentication: token verification and request identity.

Clerk is the identity provider. This package verifies Clerk-issued session tokens on
protected backend routes and maps `sub` (Clerk user id) onto the internal PostgreSQL `User`.
Application passwords are never stored or accepted.
"""

from app.auth.dependencies import CurrentUser, get_current_user
from app.auth.errors import AuthenticationError, AuthorizationError
from app.auth.identity import ClerkIdentity
from app.auth.tokens import ClerkTokenVerifier, StaticTokenVerifier, TokenVerifier

__all__ = [
    "AuthenticationError",
    "AuthorizationError",
    "ClerkIdentity",
    "ClerkTokenVerifier",
    "CurrentUser",
    "StaticTokenVerifier",
    "TokenVerifier",
    "get_current_user",
]
