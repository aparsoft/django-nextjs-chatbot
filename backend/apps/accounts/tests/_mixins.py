"""Shared test helper mixin for accounts test suite.

Provides reusable factory methods for creating users and contacts
with unique identifiers to avoid collisions when running with --keepdb.
"""

from django.contrib.auth import get_user_model

from accounts.models.custom_user import UserContact
from core.models import Country

User = get_user_model()

_uid_counter = 0


def _next_id():
    """Return a monotonically increasing integer unique across the test run."""
    global _uid_counter
    _uid_counter += 1
    return _uid_counter


class AccountsTestMixin:
    """Mixin providing factory helpers for accounts model and API tests."""

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    @staticmethod
    def create_user(role="user", **kwargs):
        """Create a basic user with unique username/email."""
        n = _next_id()
        defaults = {
            "username": f"testuser_{n}",
            "email": f"user{n}@test.com",
            "first_name": f"First{n}",
            "last_name": f"Last{n}",
            "role": role,
        }
        defaults.update(kwargs)
        user = User.objects.create_user(
            username=defaults["username"],
            email=defaults["email"],
            password="testpass123!",
            first_name=defaults["first_name"],
            last_name=defaults["last_name"],
        )
        user.role = role
        user.save(update_fields=["role"])
        return user

    @classmethod
    def create_admin_user(cls, **kwargs):
        """Create an admin user."""
        return cls.create_user(role="admin", **kwargs)

    @classmethod
    def create_superuser(cls, **kwargs):
        """Create a superuser (staff + superuser)."""
        n = _next_id()
        defaults = {
            "username": f"superuser_{n}",
            "email": f"super{n}@test.com",
            "first_name": "Super",
            "last_name": "Admin",
        }
        defaults.update(kwargs)
        user = User.objects.create_superuser(
            username=defaults["username"],
            email=defaults["email"],
            password="testpass123!",
            first_name=defaults["first_name"],
            last_name=defaults["last_name"],
        )
        user.role = "admin"
        user.save(update_fields=["role"])
        return user

    # ------------------------------------------------------------------
    # Contacts
    # ------------------------------------------------------------------

    @staticmethod
    def create_user_contact(user=None, **kwargs):
        """Create a UserContact for the given user (or a new one)."""
        if user is None:
            user = AccountsTestMixin.create_user()
        n = _next_id()
        defaults = {
            "user": user,
            "city": f"City{n}",
            "state": "TestState",
            "timezone": "Asia/Kolkata",
        }
        defaults.update(kwargs)
        return UserContact.objects.create(**defaults)

    @staticmethod
    def get_default_country():
        """Return the default country (pk=1) or create one."""
        try:
            return Country.objects.get(pk=1)
        except Country.DoesNotExist:
            return Country.objects.create(
                id=1, name="India", code="IN", phone_code="+91", is_active=True
            )
