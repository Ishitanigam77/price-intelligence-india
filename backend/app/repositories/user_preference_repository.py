"""Repository for `UserPreference`."""

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.models.user_preference import UserPreference
from app.repositories.base import BaseRepository


class UserPreferenceRepository(BaseRepository[UserPreference]):
    model = UserPreference

    def get_by_user_id(self, user_id: uuid.UUID) -> UserPreference | None:
        stmt = select(UserPreference).where(UserPreference.user_id == user_id)
        return self.session.scalars(stmt).first()

    def ensure_for_user(self, user_id: uuid.UUID) -> UserPreference:
        existing = self.get_by_user_id(user_id)
        if existing is not None:
            return existing
        preference = UserPreference(
            user_id=user_id, email_alerts_enabled=True, default_currency="INR"
        )
        try:
            with self.session.begin_nested():
                self.session.add(preference)
                self.session.flush()
            return preference
        except IntegrityError:
            existing = self.get_by_user_id(user_id)
            if existing is None:
                raise
            return existing
