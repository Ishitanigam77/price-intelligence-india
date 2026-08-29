"""Verified Clerk identity claims used to map to an internal user.

Never constructed from a client-supplied user id. Callers must obtain this from
`ClerkTokenVerifier.verify` (or a test double of that verifier).
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ClerkIdentity:
    """Claims extracted from a verified Clerk session token."""

    clerk_user_id: str
    email: str | None = None
    display_name: str | None = None
    session_id: str | None = None
