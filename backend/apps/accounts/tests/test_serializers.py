"""Tests for accounts serializers."""

from django.test import TestCase
from django.contrib.auth import get_user_model

from accounts.api.serializers.custom_user_serializers import (
    CustomUserSerializer,
    CustomUserListSerializer,
    CustomUserCreateSerializer,
    CustomUserUpdateSerializer,
    UserContactSerializer,
    UserContactCreateSerializer,
    UserContactUpdateSerializer,
)
from accounts.models.custom_user import UserContact

from . import AccountsTestMixin

User = get_user_model()


class CustomUserSerializerTests(AccountsTestMixin, TestCase):
    """Tests for CustomUser read serializers."""

    def test_list_serializer_fields(self):
        """List serializer includes lightweight fields only."""
        user = self.create_user()
        data = CustomUserListSerializer(user).data
        self.assertIn("id", data)
        self.assertIn("email", data)
        self.assertIn("full_name", data)
        self.assertIn("role", data)
        self.assertNotIn("login_count", data)
        self.assertNotIn("contact", data)

    def test_read_serializer_includes_contact(self):
        """Full read serializer includes nested contact."""
        user = self.create_user()
        self.create_user_contact(user=user)
        data = CustomUserSerializer(user).data
        self.assertIn("contact", data)
        self.assertIsInstance(data["contact"], dict)

    def test_read_serializer_full_name(self):
        """Read serializer includes full_name."""
        user = self.create_user(first_name="Grace", last_name="Hopper")
        data = CustomUserSerializer(user).data
        self.assertEqual(data["full_name"], "Grace Hopper")

    def test_read_serializer_read_only_fields(self):
        """Read-only fields are present but cannot be written."""
        user = self.create_user()
        data = CustomUserSerializer(user).data
        self.assertIn("date_joined", data)
        self.assertIn("login_count", data)
        self.assertIn("email_verified", data)


class CustomUserCreateSerializerTests(AccountsTestMixin, TestCase):
    """Tests for CustomUserCreateSerializer."""

    def test_create_user_success(self):
        """Valid data creates a user with hashed password."""
        data = {
            "email": "new@test.com",
            "username": "newuser",
            "password": "strongpass123!",
            "first_name": "New",
            "last_name": "User",
            "role": "user",
        }
        serializer = CustomUserCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()
        self.assertEqual(user.email, "new@test.com")
        self.assertTrue(user.check_password("strongpass123!"))

    def test_create_duplicate_email_fails(self):
        """Duplicate email is rejected."""
        self.create_user(email="taken@test.com")
        data = {
            "email": "taken@test.com",
            "username": "other",
            "password": "strongpass123!",
            "first_name": "A",
            "last_name": "B",
        }
        serializer = CustomUserCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("email", serializer.errors)

    def test_create_missing_password_fails(self):
        """Missing password is rejected."""
        data = {
            "email": "nopass@test.com",
            "username": "nopass",
            "first_name": "A",
            "last_name": "B",
        }
        serializer = CustomUserCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("password", serializer.errors)


class CustomUserUpdateSerializerTests(AccountsTestMixin, TestCase):
    """Tests for CustomUserUpdateSerializer."""

    def test_partial_update_username(self):
        """Partial update changes only the provided fields."""
        user = self.create_user(username="original")
        serializer = CustomUserUpdateSerializer(
            user, data={"username": "updated"}, partial=True
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()
        self.assertEqual(user.username, "updated")

    def test_update_email_dedup(self):
        """Updating to an existing email is rejected."""
        self.create_user(email="other@test.com")
        user = self.create_user(email="mine@test.com")
        serializer = CustomUserUpdateSerializer(
            user, data={"email": "other@test.com"}, partial=True
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("email", serializer.errors)

    def test_update_keep_own_email(self):
        """Updating with the user's own email is allowed."""
        user = self.create_user(email="mine@test.com")
        serializer = CustomUserUpdateSerializer(
            user, data={"email": "mine@test.com"}, partial=True
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)


class UserContactSerializerTests(AccountsTestMixin, TestCase):
    """Tests for UserContact serializers."""

    def test_read_serializer_country_name(self):
        """Read serializer resolves country_name."""
        country = self.get_default_country()
        user = self.create_user()
        contact = self.create_user_contact(user=user)
        contact.country = country
        contact.save()

        data = UserContactSerializer(contact).data
        self.assertEqual(data["country_name"], "India")

    def test_read_serializer_country_name_null(self):
        """country_name is null when no country is set."""
        user = self.create_user()
        contact = self.create_user_contact(user=user)
        data = UserContactSerializer(contact).data
        self.assertIsNone(data["country_name"])

    def test_create_serializer_fields(self):
        """Create serializer accepts the expected writable fields."""
        data = {
            "city": "Mumbai",
            "state": "Maharashtra",
            "timezone": "Asia/Kolkata",
        }
        serializer = UserContactCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_update_serializer_all_optional(self):
        """Update serializer accepts partial data."""
        data = {"city": "Pune"}
        serializer = UserContactUpdateSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
