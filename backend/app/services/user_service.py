"""User mapping: Clerk identity → internal PostgreSQL user, including preferences.

Idempotent: repeated calls with the same `clerk_user_id` return the same row. Email/display
name from verified Clerk claims are synced when present. Passwords are never stored.
"""

from app.auth.identity import ClerkIdentity
from app.db.models.user import User
from app.db.models.user_preference import UserPreference
from app.repositories.user_preference_repository import UserPreferenceRepository
from app.repositories.user_repository import UserRepository


class UserService:
    def __init__(
        self,
        users: UserRepository,
        preferences: UserPreferenceRepository,
    ) -> None:
        self._users = users
        self._preferences = preferences

    def get_or_create_from_identity(self, identity: ClerkIdentity) -> User:
        user = self._users.get_by_clerk_user_id(identity.clerk_user_id)
        if user is None:
            user = self._users.create_from_identity(identity)
        else:
            self._sync_profile_fields(user, identity)
        self._preferences.ensure_for_user(user.id)
        return user

    def get_preference(self, user: User) -> UserPreference:
        return self._preferences.ensure_for_user(user.id)

    def update_profile(
        self,
        user: User,
        *,
        display_name: str | None = None,
        email_alerts_enabled: bool | None = None,
        default_currency: str | None = None,
    ) -> tuple[User, UserPreference]:
        """Update user-owned profile fields. Clerk identity fields are not writable here."""
        if display_name is not None:
            user.display_name = display_name
        preference = self._preferences.ensure_for_user(user.id)
        if email_alerts_enabled is not None:
            preference.email_alerts_enabled = email_alerts_enabled
        if default_currency is not None:
            preference.default_currency = default_currency
        self._users.session.flush()
        return user, preference

    def _sync_profile_fields(self, user: User, identity: ClerkIdentity) -> None:
        changed = False
        if identity.email and identity.email != user.email:
            user.email = identity.email
            changed = True
        if identity.display_name and not user.display_name:
            user.display_name = identity.display_name
            changed = True
        if changed:
            self._users.session.flush()
