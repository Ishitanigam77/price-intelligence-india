"""Unit tests for Clerk JWT verification. Uses locally generated RSA keys — not live Clerk."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.auth.errors import AuthenticationError
from app.auth.tokens import ClerkTokenVerifier, decode_clerk_payload, identity_from_payload
from app.core.config import Settings


def _rsa_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def _token(
    private_key, *, sub: str = "user_clerk_abc", extra: dict | None = None, expired: bool = False
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": sub,
        "exp": now - timedelta(minutes=5) if expired else now + timedelta(minutes=5),
        "iat": now,
        "iss": "https://example.clerk.accounts.dev",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, private_key, algorithm="RS256")


def test_decode_valid_token_returns_payload() -> None:
    private_key, public_key = _rsa_keypair()
    token = _token(private_key, extra={"email": "owner@example.test", "name": "Ada"})
    payload = decode_clerk_payload(
        token, key=public_key, issuer="https://example.clerk.accounts.dev"
    )
    identity = identity_from_payload(payload)
    assert identity.clerk_user_id == "user_clerk_abc"
    assert identity.email == "owner@example.test"
    assert identity.display_name == "Ada"


def test_expired_token_is_rejected() -> None:
    private_key, public_key = _rsa_keypair()
    token = _token(private_key, expired=True)
    with pytest.raises(AuthenticationError, match="Invalid or expired"):
        decode_clerk_payload(token, key=public_key)


def test_token_signed_with_a_different_key_is_rejected() -> None:
    private_key, _ = _rsa_keypair()
    _, other_public = _rsa_keypair()
    token = _token(private_key)
    with pytest.raises(AuthenticationError, match="Invalid or expired"):
        decode_clerk_payload(token, key=other_public)


def test_issuer_mismatch_is_rejected() -> None:
    private_key, public_key = _rsa_keypair()
    token = _token(private_key)
    with pytest.raises(AuthenticationError, match="Invalid or expired"):
        decode_clerk_payload(token, key=public_key, issuer="https://other.clerk.accounts.dev")


def test_missing_sub_is_rejected() -> None:
    with pytest.raises(AuthenticationError):
        identity_from_payload({"exp": 1})


def test_verifier_fails_closed_when_jwks_is_not_configured() -> None:
    settings = Settings(_env_file=None, clerk_jwks_url="")
    verifier = ClerkTokenVerifier(settings)
    assert verifier.is_configured is False
    with pytest.raises(AuthenticationError, match="not configured"):
        verifier.verify("any.token.value")


def test_verifier_uses_jwks_client_and_returns_identity() -> None:
    private_key, public_key = _rsa_keypair()
    token = _token(private_key, extra={"email": "mapped@example.test"})

    class _Key:
        key = public_key

    class _Client:
        def get_signing_key_from_jwt(self, _token: str) -> _Key:
            return _Key()

    settings = Settings(
        _env_file=None,
        clerk_jwks_url="https://example.clerk.accounts.dev/.well-known/jwks.json",
        clerk_issuer="https://example.clerk.accounts.dev",
    )
    verifier = ClerkTokenVerifier(settings, jwk_client_factory=lambda _url: _Client())
    identity = verifier.verify(token)
    assert identity.clerk_user_id == "user_clerk_abc"
    assert identity.email == "mapped@example.test"
