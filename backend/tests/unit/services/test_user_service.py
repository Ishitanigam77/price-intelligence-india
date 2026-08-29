"""Unit tests for idempotent Clerk → internal user mapping."""

from types import SimpleNamespace
from uuid import uuid4

from app.auth.identity import ClerkIdentity
from app.services.user_service import UserService


class _FakeUserRepo:
    def __init__(self) -> None:
        self.by_clerk: dict[str, SimpleNamespace] = {}
        self.session = SimpleNamespace(flush=lambda: None)

    def get_by_clerk_user_id(self, clerk_user_id: str):
        return self.by_clerk.get(clerk_user_id)

    def create_from_identity(self, identity: ClerkIdentity):
        user = SimpleNamespace(
            id=uuid4(),
            clerk_user_id=identity.clerk_user_id,
            email=identity.email,
            display_name=identity.display_name,
        )
        self.by_clerk[identity.clerk_user_id] = user
        return user


class _FakePrefRepo:
    def __init__(self) -> None:
        self.seen: set = set()

    def ensure_for_user(self, user_id):
        self.seen.add(user_id)
        return SimpleNamespace(user_id=user_id, email_alerts_enabled=True, default_currency="INR")


def test_get_or_create_is_idempotent_for_the_same_clerk_id() -> None:
    users = _FakeUserRepo()
    prefs = _FakePrefRepo()
    service = UserService(users, prefs)
    identity = ClerkIdentity(clerk_user_id="user_same", email="a@example.test")

    first = service.get_or_create_from_identity(identity)
    second = service.get_or_create_from_identity(identity)

    assert first is second
    assert first.clerk_user_id == "user_same"
    assert len(users.by_clerk) == 1


def test_client_supplied_user_id_is_not_used_as_clerk_identity() -> None:
    users = _FakeUserRepo()
    service = UserService(users, _FakePrefRepo())
    forged = ClerkIdentity(clerk_user_id="user_real", email="real@example.test")
    user = service.get_or_create_from_identity(forged)
    assert user.clerk_user_id == "user_real"
    assert "user_attacker" not in users.by_clerk
