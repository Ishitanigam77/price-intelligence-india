"""Authenticated user profile: retrieve and update fields this application owns.

Clerk remains the identity provider. Passwords are never stored or accepted. `clerk_user_id`
is read-only and comes from the verified session, not the request body.
"""

from fastapi import APIRouter

from app.api.deps import UserServiceDep
from app.auth.dependencies import CurrentUser
from app.schemas.user import PreferenceRead, UserProfileRead, UserProfileUpdate

router = APIRouter(prefix="/me", tags=["me"])


def _profile(user, preference) -> UserProfileRead:
    return UserProfileRead(
        id=user.id,
        clerk_user_id=user.clerk_user_id,
        email=user.email,
        display_name=user.display_name,
        preferences=PreferenceRead.model_validate(preference),
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.get("", response_model=UserProfileRead)
def get_me(user: CurrentUser, user_service: UserServiceDep) -> UserProfileRead:
    preference = user_service.get_preference(user)
    return _profile(user, preference)


@router.patch("", response_model=UserProfileRead)
def update_me(
    payload: UserProfileUpdate,
    user: CurrentUser,
    user_service: UserServiceDep,
) -> UserProfileRead:
    prefs = payload.preferences
    user, preference = user_service.update_profile(
        user,
        display_name=payload.display_name,
        email_alerts_enabled=prefs.email_alerts_enabled if prefs else None,
        default_currency=prefs.normalized_currency() if prefs else None,
    )
    return _profile(user, preference)
