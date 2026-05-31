"""Tests for authentication views — login, refresh, verify, logout, register, CSRF.

Tests the auth endpoints under /api/v1/accounts/auth/:
  POST auth/login/                      — obtain token pair + user data + cookies
  POST auth/refresh/                    — rotate access/refresh tokens
  POST auth/verify/                     — verify an access token
  POST auth/logout/                     — blacklist refresh token + clear cookies
  POST auth/register/                   — create user + return tokens
  GET  auth/csrf/                       — obtain CSRF token cookie
  POST auth/password/change/            — change password (authenticated)
  POST auth/password/reset/             — request password reset
  POST auth/password/reset/confirm/     — confirm password reset
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from . import AccountsTestMixin

User = get_user_model()

LOGIN_URL = "/api/v1/accounts/auth/login/"
REFRESH_URL = "/api/v1/accounts/auth/refresh/"
VERIFY_URL = "/api/v1/accounts/auth/verify/"
LOGOUT_URL = "/api/v1/accounts/auth/logout/"
REGISTER_URL = "/api/v1/accounts/auth/register/"
CSRF_URL = "/api/v1/accounts/auth/csrf/"
PASSWORD_CHANGE_URL = "/api/v1/accounts/auth/password/change/"
PASSWORD_RESET_URL = "/api/v1/accounts/auth/password/reset/"
PASSWORD_RESET_CONFIRM_URL = "/api/v1/accounts/auth/password/reset/confirm/"


# =============================================================================
# Login Tests
# =============================================================================


class LoginViewTests(AccountsTestMixin, TestCase):
    """Tests for POST /auth/login/ (CustomTokenObtainPairView)."""

    def setUp(self):
        self.client = APIClient()
        self.user = self.create_user(
            email="login@test.com", password="testpass123!"
        )
        # Force-verify email so login works without email verification check
        self.user.email_verified = True
        self.user.save(update_fields=["email_verified"])

    def test_login_success(self):
        """Login with valid credentials returns tokens + user data."""
        resp = self.client.post(
            LOGIN_URL,
            {"email": "login@test.com", "password": "testpass123!"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("tokens", resp.data["data"])
        self.assertIn("access", resp.data["data"]["tokens"])
        self.assertIn("refresh", resp.data["data"]["tokens"])
        self.assertIn("user", resp.data["data"])
        self.assertEqual(resp.data["data"]["user"]["email"], "login@test.com")

    def test_login_sets_cookies(self):
        """Login sets access_token, refresh_token, and auth_state cookies."""
        resp = self.client.post(
            LOGIN_URL,
            {"email": "login@test.com", "password": "testpass123!"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # resp.cookies is a dict of cookie_name → cookie
        self.assertIn("access_token", resp.cookies)
        self.assertIn("refresh_token", resp.cookies)
        self.assertIn("auth_state", resp.cookies)

    def test_login_access_token_cookie_is_httponly(self):
        """access_token cookie is httpOnly (not readable by JS)."""
        resp = self.client.post(
            LOGIN_URL,
            {"email": "login@test.com", "password": "testpass123!"},
        )
        access_cookie = resp.cookies.get("access_token")
        self.assertIsNotNone(access_cookie)
        self.assertTrue(access_cookie["httponly"])

    def test_login_refresh_token_cookie_is_httponly(self):
        """refresh_token cookie is httpOnly."""
        resp = self.client.post(
            LOGIN_URL,
            {"email": "login@test.com", "password": "testpass123!"},
        )
        refresh_cookie = resp.cookies.get("refresh_token")
        self.assertIsNotNone(refresh_cookie)
        self.assertTrue(refresh_cookie["httponly"])

    def test_login_wrong_password(self):
        """Login with wrong password returns 401."""
        resp = self.client.post(
            LOGIN_URL,
            {"email": "login@test.com", "password": "wrongpass!"},
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_nonexistent_user(self):
        """Login with unknown email returns 401."""
        resp = self.client.post(
            LOGIN_URL,
            {"email": "nobody@test.com", "password": "testpass123!"},
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_missing_fields(self):
        """Login with missing fields returns 400."""
        resp = self.client.post(LOGIN_URL, {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_updates_login_count(self):
        """Successful login increments login_count."""
        self.assertEqual(self.user.login_count, 0)
        self.client.post(
            LOGIN_URL,
            {"email": "login@test.com", "password": "testpass123!"},
        )
        self.user.refresh_from_db()
        self.assertGreaterEqual(self.user.login_count, 1)

    def test_login_updates_last_active(self):
        """Successful login sets last_active timestamp."""
        self.assertIsNone(self.user.last_active)
        self.client.post(
            LOGIN_URL,
            {"email": "login@test.com", "password": "testpass123!"},
        )
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.last_active)

    def test_login_response_includes_user_role(self):
        """Login response user object includes role."""
        resp = self.client.post(
            LOGIN_URL,
            {"email": "login@test.com", "password": "testpass123!"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["data"]["user"]["role"], "user")


# =============================================================================
# Token Refresh Tests
# =============================================================================


class TokenRefreshViewTests(AccountsTestMixin, TestCase):
    """Tests for POST /auth/refresh/ (CustomTokenRefreshView)."""

    def setUp(self):
        self.client = APIClient()
        self.user = self.create_user(
            email="refresh@test.com", password="testpass123!"
        )

    def _get_tokens(self):
        """Helper: login and return (access, refresh) tokens."""
        resp = self.client.post(
            LOGIN_URL,
            {"email": "refresh@test.com", "password": "testpass123!"},
        )
        return resp.data["data"]["tokens"]["access"], resp.data["data"]["tokens"]["refresh"]

    def test_refresh_success_with_body(self):
        """Refresh with refresh token in body returns new access token."""
        _, refresh = self._get_tokens()
        resp = self.client.post(REFRESH_URL, {"refresh": refresh})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", resp.data)

    def test_refresh_rotates_refresh_token(self):
        """Refresh returns a new refresh token when ROTATE_REFRESH_TOKENS=True."""
        _, refresh = self._get_tokens()
        resp = self.client.post(REFRESH_URL, {"refresh": refresh})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("refresh", resp.data)
        # New refresh token should differ from the old one
        self.assertNotEqual(resp.data["refresh"], refresh)

    def test_refresh_updates_cookies(self):
        """Refresh updates access_token and refresh_token cookies."""
        _, refresh = self._get_tokens()
        resp = self.client.post(REFRESH_URL, {"refresh": refresh})
        self.assertIn("access_token", resp.cookies)
        self.assertIn("refresh_token", resp.cookies)

    def test_refresh_with_cookie(self):
        """Refresh reads refresh token from cookie if not in body."""
        # Login sets the refresh_token cookie on the APIClient
        login_resp = self.client.post(
            LOGIN_URL,
            {"email": "refresh@test.com", "password": "testpass123!"},
        )
        # APIClient persists cookies across requests
        refresh_resp = self.client.post(REFRESH_URL)
        self.assertEqual(refresh_resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", refresh_resp.data)

    def test_refresh_invalid_token(self):
        """Refresh with invalid token returns 401."""
        resp = self.client.post(REFRESH_URL, {"refresh": "invalid.token.here"})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_missing_token(self):
        """Refresh with no token returns 401."""
        resp = self.client.post(REFRESH_URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_old_refresh_token_not_blacklisted(self):
        """After rotation, old refresh token still works (BLACKLIST_AFTER_ROTATION=False)."""
        _, refresh = self._get_tokens()
        # First refresh
        resp1 = self.client.post(REFRESH_URL, {"refresh": refresh})
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)

        # Old token should still work because BLACKLIST_AFTER_ROTATION = False
        resp2 = self.client.post(REFRESH_URL, {"refresh": refresh})
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)


# =============================================================================
# Token Verify Tests
# =============================================================================


class TokenVerifyViewTests(AccountsTestMixin, TestCase):
    """Tests for POST /auth/verify/ (TokenVerifyView)."""

    def setUp(self):
        self.client = APIClient()
        self.user = self.create_user(
            email="verify@test.com", password="testpass123!"
        )

    def _get_access_token(self):
        """Helper: login and return access token."""
        resp = self.client.post(
            LOGIN_URL,
            {"email": "verify@test.com", "password": "testpass123!"},
        )
        return resp.data["data"]["tokens"]["access"]

    def test_verify_valid_token(self):
        """Verify with valid access token returns 200."""
        access = self._get_access_token()
        resp = self.client.post(VERIFY_URL, {"token": access})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_verify_invalid_token(self):
        """Verify with invalid token returns 401."""
        resp = self.client.post(VERIFY_URL, {"token": "invalid.token.here"})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_verify_missing_token(self):
        """Verify with no token returns 400."""
        resp = self.client.post(VERIFY_URL)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# =============================================================================
# Logout Tests
# =============================================================================


class LogoutViewTests(AccountsTestMixin, TestCase):
    """Tests for POST /auth/logout/ (LogoutView)."""

    def setUp(self):
        self.client = APIClient()
        self.user = self.create_user(
            email="logout@test.com", password="testpass123!"
        )

    def _login(self):
        """Helper: login and return response."""
        return self.client.post(
            LOGIN_URL,
            {"email": "logout@test.com", "password": "testpass123!"},
        )

    def _get_refresh(self, login_resp):
        """Extract refresh token from login response."""
        return login_resp.data["data"]["tokens"]["refresh"]

    def test_logout_success(self):
        """Logout with valid refresh token returns 200."""
        login_resp = self._login()
        refresh = self._get_refresh(login_resp)
        resp = self.client.post(LOGOUT_URL, {"refresh": refresh})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "success")

    def test_logout_clears_cookies(self):
        """Logout clears auth_state, access_token, refresh_token cookies."""
        login_resp = self._login()
        refresh = self._get_refresh(login_resp)
        resp = self.client.post(LOGOUT_URL, {"refresh": refresh})
        # DeleteCookie sets max-age=0
        for cookie_name in ["auth_state", "access_token", "refresh_token"]:
            cookie = resp.cookies.get(cookie_name)
            if cookie:
                self.assertEqual(cookie["max-age"], 0)

    def test_logout_with_refresh_token_key(self):
        """Logout accepts 'refresh_token' as an alternative key name."""
        login_resp = self._login()
        refresh = self._get_refresh(login_resp)
        resp = self.client.post(LOGOUT_URL, {"refresh_token": refresh})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_logout_invalid_token(self):
        """Logout with invalid refresh token still returns 200 (idempotent)."""
        resp = self.client.post(LOGOUT_URL, {"refresh": "invalid.token.here"})
        # Logout should be idempotent — even invalid tokens get 200
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_logout_without_token(self):
        """Logout with no token still clears cookies and returns 200."""
        self._login()  # Sets cookies
        resp = self.client.post(LOGOUT_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "success")


# =============================================================================
# Register Tests
# =============================================================================


class RegisterViewTests(AccountsTestMixin, TestCase):
    """Tests for POST /auth/register/ (RegisterView)."""

    def setUp(self):
        self.client = APIClient()

    def test_register_success(self):
        """Register with valid data creates user and returns tokens."""
        resp = self.client.post(
            REGISTER_URL,
            {
                "email": "newuser@test.com",
                "password1": "strongpass123!",
                "password2": "strongpass123!",
                "first_name": "New",
                "last_name": "User",
            },
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn("tokens", resp.data)
        self.assertIn("access", resp.data["tokens"])
        self.assertIn("refresh", resp.data["tokens"])
        self.assertTrue(User.objects.filter(email="newuser@test.com").exists())

    def test_register_duplicate_email(self):
        """Register with existing email returns 400."""
        self.create_user(email="taken@test.com")
        resp = self.client.post(
            REGISTER_URL,
            {
                "email": "taken@test.com",
                "password1": "strongpass123!",
                "password2": "strongpass123!",
                "first_name": "Dup",
                "last_name": "User",
            },
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_password_mismatch(self):
        """Register with mismatched passwords returns 400."""
        resp = self.client.post(
            REGISTER_URL,
            {
                "email": "mismatch@test.com",
                "password1": "strongpass123!",
                "password2": "different123!",
                "first_name": "Mis",
                "last_name": "Match",
            },
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_missing_fields(self):
        """Register with missing required fields returns 400."""
        resp = self.client.post(REGISTER_URL, {"email": "empty@test.com"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_creates_user_contact(self):
        """Registration triggers signal to create UserContact."""
        self.client.post(
            REGISTER_URL,
            {
                "email": "signal@test.com",
                "password1": "strongpass123!",
                "password2": "strongpass123!",
                "first_name": "Sig",
                "last_name": "Nal",
            },
        )
        user = User.objects.get(email="signal@test.com")
        self.assertTrue(hasattr(user, "contact"))
        self.assertIsNotNone(user.contact)

    def test_register_sets_default_role(self):
        """Registration defaults role to 'user'."""
        self.client.post(
            REGISTER_URL,
            {
                "email": "role@test.com",
                "password1": "strongpass123!",
                "password2": "strongpass123!",
                "first_name": "Role",
                "last_name": "Test",
            },
        )
        user = User.objects.get(email="role@test.com")
        self.assertEqual(user.role, "user")


# =============================================================================
# CSRF Tests
# =============================================================================


class CSRFTokenViewTests(AccountsTestMixin, TestCase):
    """Tests for GET /auth/csrf/ (CSRFTokenView)."""

    def setUp(self):
        self.client = APIClient()

    def test_csrf_returns_token(self):
        """GET /auth/csrf/ returns a CSRF token."""
        resp = self.client.get(CSRF_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # CSRFTokenView returns JsonResponse, use json() to parse
        data = resp.json()
        self.assertIn("csrfToken", data)

    def test_csrf_sets_cookie(self):
        """GET /auth/csrf/ sets the csrftoken cookie."""
        resp = self.client.get(CSRF_URL)
        self.assertIn("csrftoken", resp.cookies)


# =============================================================================
# Password Change Tests (via auth endpoint)
# =============================================================================


class PasswordChangeAuthViewTests(AccountsTestMixin, TestCase):
    """Tests for POST /auth/password/change/ (PasswordChangeView)."""

    def setUp(self):
        self.client = APIClient()
        self.user = self.create_user(
            email="pwchange@test.com", password="oldpass123!"
        )

    def test_change_password_success(self):
        """Authenticated user can change password with correct old password."""
        self.client.force_authenticate(self.user)
        resp = self.client.post(
            PASSWORD_CHANGE_URL,
            {
                "current_password": "testpass123!",
                "new_password": "newpass456!",
            },
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("newpass456!"))

    def test_change_password_wrong_old(self):
        """Change password with wrong old password fails."""
        self.client.force_authenticate(self.user)
        resp = self.client.post(
            PASSWORD_CHANGE_URL,
            {
                "current_password": "wrongpass!",
                "new_password": "newpass456!",
            },
        )
        self.assertIn(resp.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED])

    def test_change_password_too_short(self):
        """Change password with short new password fails."""
        self.client.force_authenticate(self.user)
        resp = self.client.post(
            PASSWORD_CHANGE_URL,
            {
                "current_password": "testpass123!",
                "new_password": "short",
            },
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password_requires_auth(self):
        """Change password without authentication returns 401."""
        resp = self.client.post(
            PASSWORD_CHANGE_URL,
            {
                "old_password": "oldpass123!",
                "new_password": "newpass456!",
                "new_password_confirm": "newpass456!",
            },
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# =============================================================================
# Authenticated API Access Tests (Bearer + Cookie)
# =============================================================================


class BearerTokenAuthTests(AccountsTestMixin, TestCase):
    """Tests that Bearer token authentication works for API access."""

    def setUp(self):
        self.client = APIClient()
        self.user = self.create_user(
            email="bearer@test.com", password="testpass123!"
        )

    def test_bearer_header_grants_access(self):
        """Authorization: Bearer <token> grants access to protected endpoints."""
        # Get token via login
        resp = self.client.post(
            LOGIN_URL,
            {"email": "bearer@test.com", "password": "testpass123!"},
        )
        access = resp.data["data"]["tokens"]["access"]

        # Use Bearer token to access protected endpoint
        authed_client = APIClient()
        authed_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        me_resp = authed_client.get("/api/v1/accounts/users/me/")
        self.assertEqual(me_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(me_resp.data["email"], "bearer@test.com")

    def test_no_auth_returns_401(self):
        """Accessing protected endpoint without token returns 401."""
        resp = self.client.get("/api/v1/accounts/users/me/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_bearer_returns_401(self):
        """Invalid Bearer token returns 401."""
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid.token.here")
        resp = self.client.get("/api/v1/accounts/users/me/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# =============================================================================
# Full Auth Flow Integration Test
# =============================================================================


class AuthFlowIntegrationTests(AccountsTestMixin, TestCase):
    """End-to-end tests covering the full authentication lifecycle."""

    def setUp(self):
        self.client = APIClient()

    def test_full_auth_lifecycle(self):
        """Register → Login → Access → Refresh → Access → Logout."""
        # 1. Register
        reg_resp = self.client.post(
            REGISTER_URL,
            {
                "email": "lifecycle@test.com",
                "password1": "lifecycle123!",
                "password2": "lifecycle123!",
                "first_name": "Life",
                "last_name": "Cycle",
            },
        )
        self.assertEqual(reg_resp.status_code, status.HTTP_201_CREATED)

        # 2. Login
        login_resp = self.client.post(
            LOGIN_URL,
            {"email": "lifecycle@test.com", "password": "lifecycle123!"},
        )
        self.assertEqual(login_resp.status_code, status.HTTP_200_OK)
        access = login_resp.data["data"]["tokens"]["access"]
        refresh = login_resp.data["data"]["tokens"]["refresh"]

        # 3. Access protected endpoint with token
        authed_client = APIClient()
        authed_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        me_resp = authed_client.get("/api/v1/accounts/users/me/")
        self.assertEqual(me_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(me_resp.data["email"], "lifecycle@test.com")

        # 4. Refresh tokens
        refresh_resp = self.client.post(REFRESH_URL, {"refresh": refresh})
        self.assertEqual(refresh_resp.status_code, status.HTTP_200_OK)
        new_access = refresh_resp.data["access"]
        self.assertIn("refresh", refresh_resp.data)  # Rotated

        # 5. Access with new token
        authed_client.credentials(HTTP_AUTHORIZATION=f"Bearer {new_access}")
        me_resp2 = authed_client.get("/api/v1/accounts/users/me/")
        self.assertEqual(me_resp2.status_code, status.HTTP_200_OK)

        # 6. Logout
        logout_resp = self.client.post(
            LOGOUT_URL, {"refresh": refresh_resp.data["refresh"]}
        )
        self.assertEqual(logout_resp.status_code, status.HTTP_200_OK)

    def test_login_then_token_verify(self):
        """Login token passes verification."""
        self.create_user(email="verifyflow@test.com", password="testpass123!")
        login_resp = self.client.post(
            LOGIN_URL,
            {"email": "verifyflow@test.com", "password": "testpass123!"},
        )
        access = login_resp.data["data"]["tokens"]["access"]

        verify_resp = self.client.post(VERIFY_URL, {"token": access})
        self.assertEqual(verify_resp.status_code, status.HTTP_200_OK)
