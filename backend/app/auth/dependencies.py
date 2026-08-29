"""FastAPI dependencies for Clerk-authenticated identity.

Protected routes depend on `get_current_user`. Catalogue routes do not. The authenticated
internal user is always derived from a verified Clerk token, never from a client-supplied id.
"""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.auth.errors import AuthenticationError
from app.auth.identity import ClerkIdentity
from app.auth.tokens import ClerkTokenVerifier, TokenVerifier
from app.core.config import Settings, get_settings
from app.db.models.user import User
from app.db.session import get_db
from app.repositories.user_preference_repository import UserPreferenceRepository
from app.repositories.user_repository import UserRepository
from app.services.user_service import UserService

_BEARER_PREFIX = "bearer "


def extract_bearer_token(request: Request) -> str | None:
    """Return the raw bearer token from `Authorization`, or `None` if absent/malformed."""
    header = request.headers.get("authorization") or request.headers.get("Authorization")
    if header is None:
        return None
    stripped = header.strip()
    if len(stripped) < len(_BEARER_PREFIX) or not stripped.lower().startswith(_BEARER_PREFIX):
        return None
    token = stripped[len(_BEARER_PREFIX) :].strip()
    return token or None


def get_token_verifier(settings: Annotated[Settings, Depends(get_settings)]) -> TokenVerifier:
    """Build the process Clerk verifier from environment-backed settings."""
    return ClerkTokenVerifier(settings)


def get_user_service(db: Annotated[Session, Depends(get_db)]) -> UserService:
    return UserService(UserRepository(db), UserPreferenceRepository(db))


def get_current_identity(
    request: Request,
    verifier: Annotated[TokenVerifier, Depends(get_token_verifier)],
) -> ClerkIdentity:
    """Verify the request's Clerk session token. Does not touch the database."""
    token = extract_bearer_token(request)
    if token is None:
        raise AuthenticationError("Authentication required.")
    return verifier.verify(token)


def get_current_user(
    identity: Annotated[ClerkIdentity, Depends(get_current_identity)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> User:
    """Map the verified Clerk identity onto the internal user (idempotent upsert)."""
    return user_service.get_or_create_from_identity(identity)


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentIdentity = Annotated[ClerkIdentity, Depends(get_current_identity)]
