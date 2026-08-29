"""Helpers for Phase 12 authorization tests."""

from app.auth.identity import ClerkIdentity


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register_identity(
    token_mapping: dict,
    token: str,
    *,
    clerk_user_id: str,
    email: str | None = None,
    display_name: str | None = None,
) -> str:
    token_mapping[token] = ClerkIdentity(
        clerk_user_id=clerk_user_id,
        email=email,
        display_name=display_name,
    )
    return token
