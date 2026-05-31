"""Tests for accounts API ViewSets — CRUD, custom actions, permissions.

Tests the action-based ViewSet endpoints auto-discovered by DefaultRouter:
  /api/v1/accounts/users/                   — CRUD
  /api/v1/accounts/users/me/                — me (detail=False)
  /api/v1/accounts/users/{id}/verify-email/ — verify_email (detail=True)
  /api/v1/accounts/users/{id}/change-password/ — change_password (detail=True)
  /api/v1/accounts/users/{id}/profile-image/   — profile_image (detail=True)
  /api/v1/accounts/users/stats/             — stats (detail=False)
  /api/v1/accounts/user-contacts/           — CRUD
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from . import AccountsTestMixin

User = get_user_model()

USERS_URL = "/api/v1/accounts/users/"
CONTACTS_URL = "/api/v1/accounts/user-contacts/"


class CustomUserViewSetCRUDTests(AccountsTestMixin, TestCase):
    """Tests for basic CRUD operations on CustomUserViewSet."""

    def setUp(self):
        self.client = APIClient()
        self.admin = self.create_admin_user()
        self.user = self.create_user()

    def test_list_users_as_admin(self):
        """Admin sees all users."""
        self.client.force_authenticate(self.admin)
        resp = self.client.get(USERS_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["results"]), 2)

    def test_list_users_as_regular(self):
        """Regular user sees only themselves."""
        self.client.force_authenticate(self.user)
        resp = self.client.get(USERS_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["results"]), 1)
        self.assertEqual(resp.data["results"][0]["id"], self.user.id)

    def test_retrieve_own_user(self):
        """User can retrieve their own record."""
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{USERS_URL}{self.user.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["email"], self.user.email)

    def test_retrieve_other_user_forbidden(self):
        """Regular user cannot retrieve another user's record."""
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{USERS_URL}{self.admin.id}/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_user_as_admin(self):
        """Admin can create a new user."""
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            USERS_URL,
            {
                "email": "new@test.com",
                "username": "newuser",
                "password": "strongpass123!",
                "first_name": "New",
                "last_name": "User",
                "role": "user",
            },
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["email"], "new@test.com")

    def test_update_user_as_admin(self):
        """Admin can partial-update a user."""
        self.client.force_authenticate(self.admin)
        resp = self.client.patch(
            f"{USERS_URL}{self.user.id}/",
            {"first_name": "Updated"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["first_name"], "Updated")

    def test_delete_user_as_admin(self):
        """Admin can delete a user."""
        self.client.force_authenticate(self.admin)
        resp = self.client.delete(f"{USERS_URL}{self.user.id}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)


class CustomUserViewSetActionTests(AccountsTestMixin, TestCase):
    """Tests for custom @action routes on CustomUserViewSet."""

    def setUp(self):
        self.client = APIClient()
        self.user = self.create_user()
        self.admin = self.create_admin_user()

    # ---- /users/me/ ----

    def test_me_returns_current_user(self):
        """GET /users/me/ returns the authenticated user's profile."""
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{USERS_URL}me/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["id"], self.user.id)
        self.assertEqual(resp.data["email"], self.user.email)

    def test_me_requires_auth(self):
        """GET /users/me/ returns 401 for anonymous."""
        resp = self.client.get(f"{USERS_URL}me/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    # ---- /users/{id}/verify-email/ ----

    def test_verify_email_action(self):
        """POST /users/{id}/verify-email/ marks email as verified."""
        self.client.force_authenticate(self.admin)
        self.assertFalse(self.user.email_verified)
        resp = self.client.post(f"{USERS_URL}{self.user.id}/verify-email/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.email_verified)

    # ---- /users/{id}/change-password/ ----

    def test_change_password_success(self):
        """POST /users/{id}/change-password/ with correct current password succeeds."""
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            f"{USERS_URL}{self.user.id}/change-password/",
            {"current_password": "testpass123!", "new_password": "newpass123!"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("newpass123!"))

    def test_change_password_wrong_current(self):
        """POST change-password with wrong current password fails."""
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            f"{USERS_URL}{self.user.id}/change-password/",
            {"current_password": "wrongpass!", "new_password": "newpass123!"},
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ---- /users/{id}/profile-image/ ----

    def test_profile_image_no_image(self):
        """GET /users/{id}/profile-image/ returns info when no image."""
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{USERS_URL}{self.user.id}/profile-image/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("status", resp.data)

    # ---- /users/stats/ ----

    def test_stats_returns_counts(self):
        """GET /users/stats/ returns aggregate statistics."""
        self.client.force_authenticate(self.admin)
        resp = self.client.get(f"{USERS_URL}stats/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("total_users", resp.data)
        self.assertIn("active_users", resp.data)
        self.assertIn("admin_users", resp.data)


class UserContactViewSetTests(AccountsTestMixin, TestCase):
    """Tests for UserContactViewSet CRUD and scoping.

    Contacts are auto-created by the post_save signal when users are created.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = self.create_user()
        self.admin = self.create_admin_user()
        # Signal already created contacts — fetch them
        self.contact = self.get_user_contact(self.user)

    def test_list_contacts_regular_user(self):
        """Regular user sees only their own contact."""
        self.client.force_authenticate(self.user)
        resp = self.client.get(CONTACTS_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["results"]), 1)

    def test_list_contacts_admin(self):
        """Admin sees all contacts."""
        other = self.create_user()  # signal creates contact for 'other'
        self.client.force_authenticate(self.admin)
        resp = self.client.get(CONTACTS_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # admin + user + other = 3 contacts
        self.assertEqual(len(resp.data["results"]), 3)

    def test_retrieve_own_contact(self):
        """User can retrieve their own contact."""
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{CONTACTS_URL}{self.contact.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_update_contact(self):
        """User can update their contact."""
        self.client.force_authenticate(self.user)
        resp = self.client.patch(
            f"{CONTACTS_URL}{self.contact.id}/",
            {"city": "Pune"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.contact.refresh_from_db()
        self.assertEqual(self.contact.city, "Pune")

    def test_create_contact_for_user(self):
        """Admin can create an additional contact record for another user.

        NOTE: The signal auto-creates one, so creating another would fail
        due to the OneToOne constraint. Instead we test retrieval + update.
        """
        other = self.create_user()
        other_contact = self.get_user_contact(other)
        self.client.force_authenticate(self.admin)
        resp = self.client.patch(
            f"{CONTACTS_URL}{other_contact.id}/",
            {"city": "Delhi", "state": "Delhi"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class SchemaGenerationTests(AccountsTestMixin, TestCase):
    """Tests that drf-spectacular schema generation doesn't crash."""

    def test_swagger_fake_view_queryset(self):
        """get_queryset() with swagger_fake_view returns empty QS."""
        from accounts.api.views.custom_user_views import CustomUserViewSet

        viewset = CustomUserViewSet()
        viewset.swagger_fake_view = True
        viewset.request = None
        viewset.format_kwarg = None

        qs = viewset.get_queryset()
        self.assertEqual(qs.count(), 0)

    def test_contact_swagger_fake_view_queryset(self):
        """UserContact get_queryset() with swagger_fake_view returns empty QS."""
        from accounts.api.views.custom_user_views import UserContactViewSet

        viewset = UserContactViewSet()
        viewset.swagger_fake_view = True
        viewset.request = None
        viewset.format_kwarg = None

        qs = viewset.get_queryset()
        self.assertEqual(qs.count(), 0)

    def test_serializer_dispatch_by_action(self):
        """get_serializer_class() returns the right serializer per action."""
        from accounts.api.views.custom_user_views import CustomUserViewSet
        from accounts.api.serializers.custom_user_serializers import (
            CustomUserListSerializer,
            CustomUserCreateSerializer,
            CustomUserUpdateSerializer,
            CustomUserSerializer,
        )

        viewset = CustomUserViewSet()

        viewset.action = "list"
        self.assertEqual(viewset.get_serializer_class(), CustomUserListSerializer)

        viewset.action = "create"
        self.assertEqual(viewset.get_serializer_class(), CustomUserCreateSerializer)

        viewset.action = "update"
        self.assertEqual(viewset.get_serializer_class(), CustomUserUpdateSerializer)

        viewset.action = "partial_update"
        self.assertEqual(viewset.get_serializer_class(), CustomUserUpdateSerializer)

        viewset.action = "retrieve"
        self.assertEqual(viewset.get_serializer_class(), CustomUserSerializer)
