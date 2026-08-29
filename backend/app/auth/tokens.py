"""Clerk session-token verification.

Verifies Clerk-issued JWTs against the instance JWKS. The Clerk secret key is never used on
the frontend and is never logged. If Clerk is not configured, verification fails closed
(401) — it never invents a successful identity.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Protocol

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWTError

from app.auth.errors import AuthenticationError
from app.auth.identity import ClerkIdentity
from app.core.config import Settings

logger = logging.getLogger(__name__)

_JWKS_TIMEOUT_SECONDS = 5.0


class TokenVerifier(Protocol):
    """Verifies a bearer token and returns the Clerk identity it represents."""

    def verify(self, token: str) -> ClerkIdentity: ...


def _display_name_from_claims(payload: dict) -> str | None:
    name = payload.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    parts = [
        part.strip()
        for part in (payload.get("given_name"), payload.get("family_name"))
        if isinstance(part, str) and part.strip()
    ]
    return " ".join(parts) or None


def decode_clerk_payload(
    token: str,
    *,
    key: object,
    issuer: str | None = None,
    audience: str | None = None,
    leeway_seconds: int = 5,
) -> dict:
    """Decode and validate a Clerk JWT with an already-resolved signing key.

    Used by `ClerkTokenVerifier` and by unit tests that supply a local RSA key. Failure always
    becomes `AuthenticationError` — never a successful identity.
    """
    options = {
        "require": ["exp", "sub"],
        "verify_aud": bool(audience),
        "verify_iss": bool(issuer),
    }
    try:
        payload = jwt.decode(
            token,
            key=key,
            algorithms=["RS256"],
            audience=audience or None,
            issuer=issuer or None,
            leeway=leeway_seconds,
            options=options,
        )
    except PyJWTError as exc:
        raise AuthenticationError("Invalid or expired authentication token.") from exc
    if not isinstance(payload, dict):
        raise AuthenticationError("Invalid or expired authentication token.")
    return payload


def identity_from_payload(payload: dict) -> ClerkIdentity:
    """Map verified JWT claims onto a `ClerkIdentity`. `sub` is the Clerk user id."""
    clerk_user_id = payload.get("sub")
    if not isinstance(clerk_user_id, str) or not clerk_user_id.strip():
        raise AuthenticationError("Invalid or expired authentication token.")
    email = payload.get("email")
    session_id = payload.get("sid")
    return ClerkIdentity(
        clerk_user_id=clerk_user_id.strip(),
        email=email.strip() if isinstance(email, str) and email.strip() else None,
        display_name=_display_name_from_claims(payload),
        session_id=(
            session_id.strip() if isinstance(session_id, str) and session_id.strip() else None
        ),
    )


class ClerkTokenVerifier:
    """Verifies Clerk session JWTs using the instance JWKS URL.

    The JWKS URL and issuer come from environment-backed settings. Missing configuration is
    treated as "cannot authenticate", not as an anonymous success.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        jwk_client_factory: Callable[[str], PyJWKClient] | None = None,
    ) -> None:
        self._jwks_url = (settings.clerk_jwks_url or "").strip()
        self._issuer = (settings.clerk_issuer or "").strip() or None
        self._audience = (settings.clerk_audience or "").strip() or None
        self._jwk_client: PyJWKClient | None = None
        if self._jwks_url:
            factory = jwk_client_factory or (
                lambda url: PyJWKClient(
                    url, cache_keys=True, lifespan=3600, timeout=_JWKS_TIMEOUT_SECONDS
                )
            )
            self._jwk_client = factory(self._jwks_url)

    @property
    def is_configured(self) -> bool:
        return self._jwk_client is not None

    def verify(self, token: str) -> ClerkIdentity:
        if not token.strip():
            raise AuthenticationError("Authentication required.")
        if self._jwk_client is None:
            logger.warning("Clerk JWKS URL is not configured; rejecting authenticated request.")
            raise AuthenticationError("Authentication is not configured.")
        try:
            signing_key = self._jwk_client.get_signing_key_from_jwt(token)
            payload = decode_clerk_payload(
                token,
                key=signing_key.key,
                issuer=self._issuer,
                audience=self._audience,
            )
        except AuthenticationError:
            raise
        except PyJWTError as exc:
            raise AuthenticationError("Invalid or expired authentication token.") from exc
        except Exception as exc:
            logger.warning("Clerk token verification failed: %s", type(exc).__name__)
            raise AuthenticationError("Invalid or expired authentication token.") from exc
        return identity_from_payload(payload)


class StaticTokenVerifier:
    """Test double: maps opaque bearer tokens onto identities. Never used in production."""

    def __init__(self, mapping: dict[str, ClerkIdentity] | None = None) -> None:
        self.mapping = mapping if mapping is not None else {}

    def verify(self, token: str) -> ClerkIdentity:
        identity = self.mapping.get(token)
        if identity is None:
            raise AuthenticationError("Invalid or expired authentication token.")
        return identity
