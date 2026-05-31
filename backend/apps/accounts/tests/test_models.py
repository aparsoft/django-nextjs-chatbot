"""Tests for CustomUser and UserContact models."""

from django.test import TestCase
from django.db import IntegrityError
from django.contrib.auth import get_user_model

from . import AccountsTestMixin

User = get_user_model()


class CustomUserModelTests(AccountsTestMixin, TestCase):
    """Tests for the CustomUser model."""

    # ---- Creation ----

    def test_create_user_defaults(self):
        """User creation sets correct defaults."""
        user = self.create_user()
        self.assertEqual(user.role, "user")
        self.assertTrue(user.is_active)
        self.assertFalse(user.email_verified)
        self.assertFalse(user.phone_verified)
        self.assertFalse(user.two_factor_enabled)
        self.assertEqual(user.login_count, 0)

    def test_create_admin_user(self):
        """Admin user has role='admin'."""
        user = self.create_admin_user()
        self.assertEqual(user.role, "admin")

    def test_create_superuser(self):
        """Superuser is staff + superuser with admin role."""
        user = self.create_superuser()
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertEqual(user.role, "admin")

    def test_email_is_username_field(self):
        """USERNAME_FIELD is email."""
        self.assertEqual(User.USERNAME_FIELD, "email")

    def test_required_fields_include_username(self):
        """REQUIRED_FIELDS includes username."""
        self.assertIn("username", User.REQUIRED_FIELDS)

    # ---- Uniqueness ----

    def test_email_must_be_unique(self):
        """Duplicate email raises IntegrityError."""
        self.create_user(email="dup@test.com")
        with self.assertRaises(IntegrityError):
            self.create_user(email="dup@test.com")

    def test_username_must_be_unique(self):
        """Duplicate username raises IntegrityError."""
        self.create_user(username="dup_user")
        with self.assertRaises(IntegrityError):
            self.create_user(username="dup_user")

    # ---- Properties and methods ----

    def test_full_name_returns_first_last(self):
        """full_name returns 'First Last' when both are set."""
        user = self.create_user(first_name="Ada", last_name="Lovelace")
        self.assertEqual(user.full_name, "Ada Lovelace")

    def test_full_name_falls_back_to_username(self):
        """full_name returns username when first_name/last_name are empty."""
        user = self.create_user(first_name="", last_name="")
        self.assertEqual(user.full_name, user.username)

    def test_is_admin_user_property(self):
        """is_admin_user returns True only for admin role."""
        admin = self.create_admin_user()
        regular = self.create_user()
        self.assertTrue(admin.is_admin_user)
        self.assertFalse(regular.is_admin_user)

    def test_verify_email(self):
        """verify_email() sets email_verified=True and returns True."""
        user = self.create_user()
        self.assertFalse(user.email_verified)
        result = user.verify_email()
        user.refresh_from_db()
        self.assertTrue(result)
        self.assertTrue(user.email_verified)

    def test_verify_email_idempotent(self):
        """verify_email() returns False if already verified."""
        user = self.create_user()
        user.verify_email()
        result = user.verify_email()
        self.assertFalse(result)

    def test_update_last_active(self):
        """update_last_active() sets last_active to now."""
        user = self.create_user()
        self.assertIsNone(user.last_active)
        user.update_last_active()
        user.refresh_from_db()
        self.assertIsNotNone(user.last_active)

    def test_str_returns_email(self):
        """__str__ returns the email address."""
        user = self.create_user(email="ada@test.com")
        self.assertEqual(str(user), "ada@test.com")

    def test_account_age_days(self):
        """account_age_days returns a positive integer."""
        user = self.create_user()
        self.assertGreaterEqual(user.account_age_days, 0)

    # ---- Role choices ----

    def test_valid_roles(self):
        """Both 'user' and 'admin' roles are accepted."""
        for role in ["user", "admin"]:
            user = self.create_user(role=role)
            self.assertEqual(user.role, role)


class UserContactModelTests(AccountsTestMixin, TestCase):
    """Tests for the UserContact model."""

    def test_create_contact(self):
        """Contact creation with defaults works."""
        user = self.create_user()
        contact = self.create_user_contact(user=user)
        self.assertEqual(contact.user, user)
        self.assertIsNotNone(contact.city)

    def test_contact_str(self):
        """__str__ includes the user's email."""
        user = self.create_user(email="contact@test.com")
        contact = self.create_user_contact(user=user)
        self.assertIn("contact@test.com", str(contact))

    def test_contact_has_timestamps(self):
        """Contact has created_at and updated_at from TimestampedModel."""
        user = self.create_user()
        contact = self.create_user_contact(user=user)
        self.assertIsNotNone(contact.created_at)
        self.assertIsNotNone(contact.updated_at)

    def test_one_to_one_relationship(self):
        """User has at most one contact."""
        user = self.create_user()
        self.create_user_contact(user=user)
        from accounts.models.custom_user import UserContact

        with self.assertRaises(IntegrityError):
            UserContact.objects.create(user=user, city="Dup")
