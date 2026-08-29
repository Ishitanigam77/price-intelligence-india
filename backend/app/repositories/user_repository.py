"""Repository for the internal `User` mapped from a Clerk identity."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.auth.identity import ClerkIdentity
from app.db.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    def get_by_clerk_user_id(self, clerk_user_id: str) -> User | None:
        stmt = select(User).where(User.clerk_user_id == clerk_user_id)
        return self.session.scalars(stmt).first()

    def create_from_identity(self, identity: ClerkIdentity) -> User:
        """Insert a user for `identity.clerk_user_id`.

        On a uniqueness race, returns the row that won rather than raising. Nested savepoint
        keeps the outer transaction usable after `IntegrityError`.
        """
        user = User(
            clerk_user_id=identity.clerk_user_id,
            email=identity.email,
            display_name=identity.display_name,
        )
        try:
            with self.session.begin_nested():
                self.session.add(user)
                self.session.flush()
            return user
        except IntegrityError:
            existing = self.get_by_clerk_user_id(identity.clerk_user_id)
            if existing is None:
                raise
            return existing
