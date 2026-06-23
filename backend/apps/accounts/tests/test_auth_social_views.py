"""Tests for Google OAuth authentication — POST /auth/social/google/ (GoogleLoginView).

Tests the ID-token verification flow:
  - Valid token → user created + our JWT tokens issued + cookies set
  - Existing user → linked, not duplicated
  - Invalid token → 401
  - Unverified email → 403
  - Missing id_token → 400
  - Audience mismatch → 401 (mocked)
  - Tokens work with Bearer auth on protected endpoints
  - Provider is recorded in social_auth_providers

All Google API calls are mocked — tests never hit Google's servers.
"""

from unittest.mock import patch

import google.oauth2.id_token  # noqa: F401 — loads submodule so patch() can find it
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from . import AccountsTestMixin

User = get_user_model()

GOOGLE_LOGIN_URL = "/api/v1/accounts/auth/social/google/"
ME_URL = "/api/v1/accounts/users/me/"

# The view does `from google.oauth2 import id_token as google_id_token` inside
# post(), then calls `google_id_token.verify_oauth2_token(...)`.  We import the
# submodule at module level (above) so it exists in sys.modules, then patch the
# function directly.
PATCH_TARGET = "google.oauth2.id_token.verify_oauth2_token"


def _make_claims(
    *,
    email="googleuser@gmail.com",
    email_verified=True,
    sub="google-sub-123",
    given_name="Google",
    family_name="User",
):
    """Build a fake Google ID-token claims dict for mocking."""
    return {
        "sub": sub,
        "email": email,
        "email_verified": email_verified,
        "given_name": given_name,
        "family_name": family_name,
        "name": f"{given_name} {family_name}",
        "picture": "https://lh3.googleusercontent.com/photo.jpg",
    }


class GoogleLoginViewTests(AccountsTestMixin, TestCase):
    """Tests for POST /auth/social/google/ (GoogleLoginView)."""

    def setUp(self):
        self.client = APIClient()

    # ------------------------------------------------------------------
    # Success cases
    # ------------------------------------------------------------------

    @patch(PATCH_TARGET)
    def test_google_login_creates_new_user(self, mock_verify):
        """Valid Google ID token creates a new user and returns our JWT tokens."""
        claims = _make_claims()
        mock_verify.return_value = claims

        resp = self.client.post(GOOGLE_LOGIN_URL, {"id_token": "fake-google-token"})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "success")
        self.assertIn("data", resp.data)
        self.assertIn("tokens", resp.data["data"])
        self.assertIn("access", resp.data["data"]["tokens"])
        self.assertIn("refresh", resp.data["data"]["tokens"])
        self.assertTrue(resp.data["data"]["created"])

        # User was created in the DB
        user = User.objects.get(email="googleuser@gmail.com")
        self.assertEqual(user.first_name, "Google")
        self.assertEqual(user.last_name, "User")
        self.assertTrue(user.email_verified)
        self.assertFalse(user.has_usable_password())

    @patch(PATCH_TARGET)
    def test_google_login_sets_cookies(self, mock_verify):
        """Google login sets access_token, refresh_token, and auth_state cookies."""
        mock_verify.return_value = _make_claims()

        resp = self.client.post(GOOGLE_LOGIN_URL, {"id_token": "fake-google-token"})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", resp.cookies)
        self.assertIn("refresh_token", resp.cookies)
        self.assertIn("auth_state", resp.cookies)
        # access and refresh must be httpOnly
        self.assertTrue(resp.cookies["access_token"]["httponly"])
        self.assertTrue(resp.cookies["refresh_token"]["httponly"])

    @patch(PATCH_TARGET)
    def test_google_login_existing_user_not_duplicated(self, mock_verify):
        """Google login for an existing user links the provider without duplicating."""
        # Pre-create a user with the same email
        self.create_user(email="googleuser@gmail.com")
        original_count = User.objects.count()

        mock_verify.return_value = _make_claims()

        resp = self.client.post(GOOGLE_LOGIN_URL, {"id_token": "fake-google-token"})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["data"]["created"])
        # No duplicate user created
        self.assertEqual(User.objects.count(), original_count)
        # The existing user's email is correct
        self.assertEqual(resp.data["data"]["user"]["email"], "googleuser@gmail.com")

    @patch(PATCH_TARGET)
    def test_google_login_records_provider(self, mock_verify):
        """Google login records 'google' in the user's social_auth_providers."""
        mock_verify.return_value = _make_claims(sub="sub-abc-999")

        resp = self.client.post(GOOGLE_LOGIN_URL, {"id_token": "fake-google-token"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        user = User.objects.get(email="googleuser@gmail.com")
        providers = user.social_auth_providers
        self.assertIn("google", providers["active_providers"])
        self.assertEqual(providers["connections"]["google"]["sub"], "sub-abc-999")

    @patch(PATCH_TARGET)
    def test_google_login_increments_login_count(self, mock_verify):
        """Google login increments the user's login_count."""
        mock_verify.return_value = _make_claims()

        self.client.post(GOOGLE_LOGIN_URL, {"id_token": "fake-google-token"})
        user = User.objects.get(email="googleuser@gmail.com")
        self.assertGreaterEqual(user.login_count, 1)

    @patch(PATCH_TARGET)
    def test_google_login_updates_last_active(self, mock_verify):
        """Google login sets the user's last_active timestamp."""
        mock_verify.return_value = _make_claims()

        self.client.post(GOOGLE_LOGIN_URL, {"id_token": "fake-google-token"})
        user = User.objects.get(email="googleuser@gmail.com")
        self.assertIsNotNone(user.last_active)

    @patch(PATCH_TARGET)
    def test_google_login_tokens_work_with_bearer(self, mock_verify):
        """Tokens issued by Google login work as Bearer auth on protected endpoints."""
        mock_verify.return_value = _make_claims()

        resp = self.client.post(GOOGLE_LOGIN_URL, {"id_token": "fake-google-token"})
        access = resp.data["data"]["tokens"]["access"]

        authed_client = APIClient()
        authed_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        me_resp = authed_client.get(ME_URL)

        self.assertEqual(me_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(me_resp.data["email"], "googleuser@gmail.com")

    @patch(PATCH_TARGET)
    def test_google_login_idempotent_provider_link(self, mock_verify):
        """Logging in twice with Google does not duplicate the provider entry."""
        claims = _make_claims()
        mock_verify.return_value = claims

        # First login
        self.client.post(GOOGLE_LOGIN_URL, {"id_token": "fake-google-token"})
        user = User.objects.get(email="googleuser@gmail.com")
        first_count = len(user.social_auth_providers["active_providers"])

        # Second login
        self.client.post(GOOGLE_LOGIN_URL, {"id_token": "fake-google-token"})
        user.refresh_from_db()
        second_count = len(user.social_auth_providers["active_providers"])

        self.assertEqual(first_count, second_count)
        self.assertEqual(second_count, 1)

    # ------------------------------------------------------------------
    # Error cases
    # ------------------------------------------------------------------

    @patch(PATCH_TARGET)
    def test_google_login_invalid_token(self, mock_verify):
        """Invalid Google ID token returns 401."""
        mock_verify.side_effect = ValueError("Invalid token")

        resp = self.client.post(GOOGLE_LOGIN_URL, {"id_token": "bad-token"})

        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(resp.data["code"], "invalid_google_token")

    @patch(PATCH_TARGET)
    def test_google_login_audience_mismatch(self, mock_verify):
        """Token with wrong audience (our client_id mismatch) returns 401."""
        # verify_oauth2_token raises ValueError when audience doesn't match
        mock_verify.side_effect = ValueError("Wrong audience")

        resp = self.client.post(GOOGLE_LOGIN_URL, {"id_token": "wrong-audience-token"})

        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch(PATCH_TARGET)
    def test_google_login_unverified_email(self, mock_verify):
        """Google account with unverified email returns 403."""
        mock_verify.return_value = _make_claims(email_verified=False)

        resp = self.client.post(GOOGLE_LOGIN_URL, {"id_token": "fake-token"})

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["code"], "email_unverified")

    def test_google_login_missing_id_token(self):
        """Request without id_token field returns 400."""
        resp = self.client.post(GOOGLE_LOGIN_URL, {})

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_google_login_empty_id_token(self):
        """Request with empty id_token string returns 400."""
        resp = self.client.post(GOOGLE_LOGIN_URL, {"id_token": ""})

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch(PATCH_TARGET)
    def test_google_login_no_user_created_on_failure(self, mock_verify):
        """Failed Google login does not create a user in the DB."""
        mock_verify.side_effect = ValueError("Invalid")

        original_count = User.objects.count()
        self.client.post(GOOGLE_LOGIN_URL, {"id_token": "bad-token"})

        self.assertEqual(User.objects.count(), original_count)

    # ------------------------------------------------------------------
    # Integration: Google login → Bearer access → Refresh → Logout
    # ------------------------------------------------------------------

    @patch(PATCH_TARGET)
    def test_google_login_full_lifecycle(self, mock_verify):
        """Google login → Bearer access → Refresh → Logout works end-to-end."""
        mock_verify.return_value = _make_claims(email="lifecycle@gmail.com")

        # 1. Google login
        login_resp = self.client.post(
            GOOGLE_LOGIN_URL, {"id_token": "fake-google-token"}
        )
        self.assertEqual(login_resp.status_code, status.HTTP_200_OK)
        access = login_resp.data["data"]["tokens"]["access"]
        refresh = login_resp.data["data"]["tokens"]["refresh"]

        # 2. Access protected endpoint with Bearer
        authed_client = APIClient()
        authed_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        me_resp = authed_client.get(ME_URL)
        self.assertEqual(me_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(me_resp.data["email"], "lifecycle@gmail.com")

        # 3. Refresh tokens
        refresh_resp = self.client.post(
            "/api/v1/accounts/auth/refresh/", {"refresh": refresh}
        )
        self.assertEqual(refresh_resp.status_code, status.HTTP_200_OK)
        new_access = refresh_resp.data["access"]
        self.assertIn("refresh", refresh_resp.data)  # rotated

        # 4. Access with new token
        authed_client.credentials(HTTP_AUTHORIZATION=f"Bearer {new_access}")
        me_resp2 = authed_client.get(ME_URL)
        self.assertEqual(me_resp2.status_code, status.HTTP_200_OK)

        # 5. Logout
        logout_resp = self.client.post(
            "/api/v1/accounts/auth/logout/",
            {"refresh": refresh_resp.data["refresh"]},
        )
        self.assertEqual(logout_resp.status_code, status.HTTP_200_OK)
