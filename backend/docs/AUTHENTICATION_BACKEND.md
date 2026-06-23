# Authentication — Django + DRF Backend (Gold-Standard Production Guide)

> The complete, production-grade reference for the authentication backend that powers the
> Next.js BFF frontend, the React Native mobile app, and direct API access. This document
> is **guide + code + workflow**: it explains *why* each decision is made, ships the *exact*
> code to implement it, and gives you a *runbook* to operate and verify it.
>
> **Pair this with** [the frontend BFF playbook](../../frontend/docs/AUTHENTICATION_PLAYBOOK.md).
> Backend = identity authority (mints/validates JWTs). Frontend = BFF proxy (owns cookies).

---

## 0. Design Principles (read first)

These are the non-negotiable rules every auth change in this codebase must respect.

1. **Django is the single identity authority.** It owns the user table, password hashing,
   token signing, and token revocation. No frontend library duplicates that state.
2. **Short access, rotating refresh.** Access tokens live 5 minutes; refresh tokens live
   1 day and rotate on every use. A leaked access token is useless within minutes.
3. **The API is transport-agnostic.** The *same* endpoints serve the web BFF (cookies),
   mobile (Keychain/Keystore), and Swagger (cookie fallback). No client-specific forks.
4. **Tokens never appear in logs or URLs.** They travel in the `Authorization` header or
   `httpOnly` cookies — never query strings, never the response of a GET.
5. **Fail closed, but log clearly.** Auth errors return generic messages to the client
   (no user-enumeration, no stack traces) and detailed structured logs to the server.
6. **OAuth issues *our* tokens.** Google/GitHub prove identity; Django still mints the
   SimpleJWT pair. The rest of the system never special-cases "social" users.
7. **Everything is tested.** Login, refresh, logout, rotation, blacklist, throttling, and
   OAuth each have tests that protect the contract.

---

## 1. Architecture Overview

```
┌──────────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐
│   Next.js Web (BFF)  │   │  React Native (app)  │   │  Swagger / Admin     │
│  httpOnly cookies    │   │  Keychain/Keystore   │   │  cookie fallback     │
└──────────┬───────────┘   └──────────┬───────────┘   └──────────┬───────────┘
           │ Authorization: Bearer <access>           cookie: access_token
           └───────────────────────────┴──────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                          Django + DRF Backend                                │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐   │
│  │  DEFAULT_AUTHENTICATION_CLASSES (tried in order):                     │   │
│  │   1. JWTAuthentication              → Bearer header (BFF + mobile)    │   │
│  │   2. CustomJWTCookieAuthentication  → access_token cookie (Swagger)   │   │
│  │   3. SessionAuthentication          → Django admin                    │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  SimpleJWT: mint / validate / rotate / blacklist                             │
│  google-auth: verify Google ID tokens → mint our JWTs (Section 9)            │
│  Throttling: per-scope rate limits (login 10–30/min)                         │
│                                                                              │
│  Django does NOT know a BFF exists. It sees standard JWT requests.           │
└──────────────────────────────────────────────────────────────────────────────┘
```

The browser never talks to Django directly in production — the Next.js BFF injects the
`Authorization` header from the cookie it owns. Mobile and Swagger are first-class too:
same tokens, same endpoints.

---

## 2. Tech Stack & Gold-Standard Libraries

Everything here is already in `backend/requirements.txt` unless marked **(add)**.

| Concern | Library | Version | Why this one |
|---|---|---|---|
| Web framework | `Django` | 6.0.5 | LTS-track, native async, mature auth/ORM. |
| API layer | `djangorestframework` | 3.17.1 | The DRF standard — serializers, viewsets, throttling. |
| **JWT** | `djangorestframework-simplejwt` | 5.5.1 | The de-facto DRF JWT lib: rotation, blacklist, claims. |
| JWT primitives | `PyJWT` + `cryptography` | 2.13.0 / 48.0.0 | Underlying encode/verify + crypto backend. |
| CORS | `django-cors-headers` | 4.9.0 | Credentialed cross-origin for the dev frontend. |
| OpenAPI | `drf-spectacular` (+ sidecar) | 0.29.0 | Typed schema → Swagger UI → client generation. |
| Filtering | `django-filter` | 25.2 | Declarative query filtering on viewsets. |
| DB driver | `psycopg` | 3.3.4 | PostgreSQL 3.x driver (async-ready). |
| HTTP client | `requests` | 2.34.2 | OAuth code-exchange calls. |
| **Social/OAuth infra** | `django-allauth` | 65.18.0 | Installed; enterprise OAuth + headless SPA mode. |

### Recommended additions for production-grade Google OAuth

| Library | Add to requirements | Role |
|---|---|---|
| **`google-auth`** | `google-auth==2.41.1` **(add)** | Official Google library to **verify ID tokens** server-side. This is the cleanest, most secure way to do "Sign in with Google" behind a BFF — see Section 9. |
| `dj-rest-auth` | `dj-rest-auth==7.0.1` *(optional)* | Only if you want allauth's batteries-included REST social endpoints instead of the lean custom endpoint. |

> **Decision:** This guide recommends the **`google-auth` ID-token verification** flow as
> the primary path (Section 9.1) because it keeps Django the identity authority with the
> least moving parts and integrates perfectly with the BFF. `django-allauth` headless
> (Section 9.3) is documented as the enterprise alternative since it's already installed.

---

## 3. Custom User Model

Email is the login identifier. The model lives in
`backend/apps/accounts/models/custom_user.py`.

```python
class CustomUser(AbstractUser):
    """Email-based custom user with role + social-auth bookkeeping."""

    ROLE_CHOICES = [("user", "User"), ("admin", "Administrator")]

    email = models.EmailField(_("email address"), unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="user")
    profile_picture = models.ImageField(upload_to="avatars/", blank=True, null=True)

    # Verification & security
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    two_factor_enabled = models.BooleanField(default=False)
    last_password_change = models.DateTimeField(auto_now_add=True)

    # Connected OAuth providers: {"active_providers": [], "connections": {}, ...}
    social_auth_providers = models.JSONField(default=helper.get_default_social_auth_providers)

    # Activity tracking
    last_active = models.DateTimeField(null=True, blank=True)
    login_count = models.PositiveIntegerField(default=0)

    USERNAME_FIELD = "email"          # ← login is by email
    REQUIRED_FIELDS = ["username"]

    class Meta:
        ordering = ["-date_joined"]
        indexes = [
            models.Index(fields=["email"], name="user_email_idx"),
            models.Index(fields=["role"], name="user_role_idx"),
            models.Index(fields=["email_verified", "last_active"], name="user_verified_active_idx"),
            GinIndex(fields=["social_auth_providers"], name="user_social_auth_gin_idx"),
        ]

    @property
    def full_name(self) -> str:
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username

    @property
    def is_admin_user(self) -> bool:
        return self.role == "admin"

    def update_last_active(self, save: bool = True) -> None:
        self.last_active = timezone.now()
        if save:
            self.save(update_fields=["last_active"])

    def verify_email(self) -> bool:
        if not self.email_verified:
            self.email_verified = True
            self.save(update_fields=["email_verified"])
            return True
        return False
```

**Why these choices**

- **`USERNAME_FIELD = "email"`** — humans authenticate with email, not a username. The
  `username` still exists (auto-generated) so legacy Django admin tooling keeps working.
- **`role`** drives coarse authorization (`user` vs `admin`) and the post-login dashboard
  route. Fine-grained permissions stay in DRF permission classes.
- **`social_auth_providers` (JSONB + GIN index)** records which OAuth providers a user has
  linked, queryable efficiently. OAuth users are *normal* users — no separate table.
- **Indexes** target the real hot paths: login (`email`), admin filters (`role`,
  `email_verified`), and activity dashboards (`last_active`).

> 🔒 **Never** set a usable password for OAuth-only users. `create_user(...)` without a
> password calls `set_unusable_password()`, so they can only sign in via their provider.

---

## 4. Settings (with rationale)

### 4.1 `DEFAULT_AUTHENTICATION_CLASSES` & throttling — `REST_FRAMEWORK`

**`config/settings/base.py`** — the foundation (header auth + admin, no cookie fallback yet):

```python
# config/settings/base.py
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",   # 1. Bearer header
        "rest_framework.authentication.SessionAuthentication",        # 2. Django admin
        "rest_framework.authentication.BasicAuthentication",           # 3. testing fallback
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/second",
        "user": "1000/second",
        "subscribe": "60/minute",
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}
```

**`config/settings/development.py`** — prepends `CustomJWTCookieAuthentication` (the cookie
fallback for Swagger/admin) and tightens throttling + adds the `login` scope:

```python
# config/settings/development.py  (overrides base)
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "accounts.services.auth.CustomJWTCookieAuthentication",   # ← cookie fallback added here
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/minute",
        "user": "200/minute",
        "login": "30/minute",       # tightened to 10/minute in production.py
    },
}
```

> ⚠️ **Order matters.** `JWTAuthentication` is first so the Bearer header (BFF + mobile)
> wins. `CustomJWTCookieAuthentication` (defined in `accounts/services/auth.py`) only engages
> when there's no header — it reads the `access_token` cookie and enforces CSRF. This is
> what makes Swagger UI and admin browser sessions work. Keep `IsAuthenticated` as the
> default permission so endpoints are **closed by default** — opt *into* `AllowAny`
> explicitly on public auth endpoints.

### 4.2 `SIMPLE_JWT`

```python
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=5),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": config("DJANGO_SECRET_KEY"),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    # Cookie names/ages consumed by CustomJWTCookieAuthentication + cookie helpers
    "AUTH_COOKIE": "access_token",
    "AUTH_COOKIE_REFRESH": "refresh_token",
    "AUTH_COOKIE_SECURE": False,          # True in production.py
    "AUTH_COOKIE_HTTP_ONLY": True,
    "AUTH_COOKIE_SAMESITE": "Lax",
    "AUTH_COOKIE_ACCESS_MAX_AGE": 300,    # 5 min — MUST match ACCESS_TOKEN_LIFETIME
    "AUTH_COOKIE_REFRESH_MAX_AGE": 86400, # 1 day — MUST match REFRESH_TOKEN_LIFETIME
}
```

| Setting | Value | Rationale |
|---|---|---|
| `ACCESS_TOKEN_LIFETIME` | 5 min | Short-lived = limited blast radius. BFF refreshes transparently. |
| `REFRESH_TOKEN_LIFETIME` | 1 day | Security/UX balance; forces a re-auth daily. |
| `ROTATE_REFRESH_TOKENS` | True | Each refresh returns a new refresh token → limits replay. |
| `BLACKLIST_AFTER_ROTATION` | False | Old refresh stays valid briefly → avoids the parallel-refresh race. Logout still blacklists explicitly. |
| `UPDATE_LAST_LOGIN` | False | Skips a DB write per token issue; `last_active` is tracked separately. |
| `SIGNING_KEY` | `DJANGO_SECRET_KEY` | HS256 symmetric signing. Rotate by rotating the secret (invalidates all tokens). |

> ✅ **Cookie max-age MUST mirror the token lifetimes.** See [Section 11](#11-known-issues--required-hardening-fixes)
> for a live inconsistency in the login view that you must fix.

### 4.3 CORS, CSRF & `AUTHENTICATION_BACKENDS`

```python
# development.py
CORS_ALLOW_CREDENTIALS = True               # cookies cross-origin
CORS_ALLOWED_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]
CSRF_TRUSTED_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]
CSRF_COOKIE_HTTPONLY = False                # JS reads it to echo X-CSRFToken
CSRF_COOKIE_SAMESITE = "Lax"

AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",            # admin + username
    "allauth.account.auth_backends.AuthenticationBackend",  # email login + OAuth
)
```

> **CORS vs CSRF division of labour.** For the **header-based** BFF/mobile flow, CORS is
> what matters and CSRF does not apply (no cookies drive the request). CSRF only matters
> for the **cookie fallback** flow (Swagger/admin), which is why `CustomJWTCookieAuthentication`
> enforces CSRF explicitly. In production, lock `CORS_ALLOWED_ORIGINS`/`CSRF_TRUSTED_ORIGINS`
> to the real frontend origin only.

---

## 5. API Endpoints

All endpoints are at `/api/v1/accounts/`.

### Token Endpoints

| Method | URL | View | Auth | Purpose |
|--------|-----|------|------|---------|
| POST | `auth/login/` | `CustomTokenObtainPairView` | AllowAny | Login → `{ data: { tokens, user } }` + sets cookies |
| POST | `auth/refresh/` | `CustomTokenRefreshView` | AllowAny | Refresh → `{access, refresh}` + updates cookies |
| POST | `auth/verify/` | `TokenVerifyView` | AllowAny | Verify access token is valid |
| POST | `auth/logout/` | `LogoutView` | AllowAny | Blacklist refresh token + clear cookies |
| POST | `auth/social/google/` | `GoogleLoginView` *(Section 9)* | AllowAny | Verify Google ID token → mint our JWTs |

### Registration & Password Management

| Method | URL | View | Auth | Purpose |
|--------|-----|------|------|---------|
| POST | `auth/register/` | `RegisterView` | AllowAny | Create new user + get tokens |
| POST | `auth/password/reset/` | `PasswordResetView` | AllowAny | Request password reset email |
| POST | `auth/password/reset/confirm/` | `PasswordResetConfirmView` | AllowAny | Confirm reset with uid+token |
| POST | `auth/password/change/` | `PasswordChangeView` | IsAuthenticated | Change password (requires current) |
| GET/POST | `auth/email/verify/` | `EmailVerificationView` | AllowAny | Verify email via uid+token |
| GET | `auth/csrf/` | `CSRFTokenView` | AllowAny | Get CSRF token cookie |

### User Management

| Method | URL | View | Auth | Purpose |
|--------|-----|------|------|---------|
| GET | `users/` | `CustomUserViewSet` | IsAuthenticated | List users (admin: all, user: self) |
| POST | `users/` | `CustomUserViewSet` | IsAuthenticated | Create user |
| GET | `users/{id}/` | `CustomUserViewSet` | IsAuthenticated | Retrieve user |
| PATCH | `users/{id}/` | `CustomUserViewSet` | IsAuthenticated | Update user |
| DELETE | `users/{id}/` | `CustomUserViewSet` | IsAuthenticated | Delete user |
| GET | `users/me/` | `@action` | IsAuthenticated | Get current user |
| POST | `users/{id}/verify-email/` | `@action` | IsAuthenticated | Verify email |
| POST | `users/{id}/change-password/` | `@action` | IsAuthenticated | Change password (action) |
| GET | `users/{id}/profile-image/` | `@action` | IsAuthenticated | Get avatar URL |
| GET | `users/stats/` | `@action` | IsAuthenticated | User counts (admin) |

### Profile

| Method | URL | View | Auth | Purpose |
|--------|-----|------|------|---------|
| GET | `profile/avatar/` | `ProfileAvatarView` | IsAuthenticated | Get avatar |
| POST | `profile/avatar/` | `ProfileAvatarView` | IsAuthenticated | Upload avatar |
| DELETE | `profile/avatar/` | `ProfileAvatarView` | IsAuthenticated | Remove avatar |

**Total: 22 endpoints**

---

## 6. Authentication Classes

DRF tries each class in order until one returns a `(user, auth)` pair.

| Priority | Class | Trigger | Used by |
|---|---|---|---|
| 1 | `JWTAuthentication` | `Authorization: Bearer <token>` header | BFF proxy, mobile |
| 2 | `CustomJWTCookieAuthentication` | `access_token` cookie (no header) | Swagger, admin browser |
| 3 | `SessionAuthentication` | Django session cookie | Django admin |

### `CustomJWTCookieAuthentication`

The cookie fallback extends SimpleJWT's `JWTAuthentication`: if there's no `Authorization`
header, it reads the access token from the `access_token` cookie and **enforces CSRF**
(because cookie-driven requests are CSRF-eligible, unlike header-driven ones).

```python
# backend/apps/accounts/services/auth.py
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.authentication import CSRFCheck
from rest_framework import exceptions
from django.conf import settings


class CustomJWTCookieAuthentication(JWTAuthentication):
    """JWT auth that falls back to the access_token cookie and enforces CSRF."""

    def authenticate(self, request):
        header = self.get_header(request)

        if header is None:
            cookie_name = settings.SIMPLE_JWT.get("AUTH_COOKIE", "access_token")
            raw_token = request.COOKIES.get(cookie_name)
            if not raw_token:
                return None
        else:
            raw_token = self.get_raw_token(header)
            if raw_token is None:
                return None

        validated_token = self.get_validated_token(raw_token)
        user = self.get_user(validated_token)
        user.update_last_active(save=True)
        return user, validated_token

    def enforce_csrf(self, request):
        check = CSRFCheck()
        check.process_request(request)
        reason = check.process_view(request, None, (), {})
        if reason:
            raise exceptions.PermissionDenied(f"CSRF Failed: {reason}")
```

> 🔑 **Why a custom class?** Stock SimpleJWT only reads the header. Swagger and the admin
> browser send cookies, not headers — without this fallback, "Try it out" in Swagger would
> fail. The BFF and mobile never hit this path because they always send the header.

---

## 7. Core Code — Serializers, Views & Cookie Helpers

### 7.1 Token serializers (`accounts/api/serializers/auth_serializers.py`)

```python
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Login serializer: authenticates by email and bundles user profile data."""

    username_field = User.EMAIL_FIELD  # ← email, not username

    def validate(self, attrs):
        data = super().validate(attrs)  # raises AuthenticationFailed on bad creds
        data["user"] = {
            "id": self.user.id,
            "email": self.user.email,
            "first_name": self.user.first_name,
            "last_name": self.user.last_name,
            "full_name": self.user.full_name,
            "role": self.user.role,
            "status": "active" if self.user.is_active else "inactive",
            "email_verified": self.user.email_verified,
        }
        return data


class CustomTokenRefreshSerializer(TokenRefreshSerializer):
    """Refresh serializer: accepts the refresh token from body OR the cookie."""

    refresh = serializers.CharField(required=False)

    def validate(self, attrs):
        cookie_refresh = self.context["request"].COOKIES.get("refresh_token")
        if cookie_refresh:
            attrs["refresh"] = cookie_refresh
        if not attrs.get("refresh"):
            raise InvalidToken("No valid refresh token found")
        return super().validate(attrs)
```

> The login serializer deliberately bundles a small, safe user object so the BFF can render
> the shell without a second round-trip. It contains **no secrets** — never embed tokens,
> password hashes, or internal flags here.

### 7.2 Cookie helper (single source of truth)

The login and refresh views both set cookies. **Centralize that logic** so the two can
never drift (this is the fix for the inconsistency in [Section 11](#11-known-issues--required-hardening-fixes)).

```python
# backend/apps/accounts/services/cookies.py  (recommended new module)
from django.conf import settings


def _opts():
    sj = settings.SIMPLE_JWT
    return {
        "httponly": sj.get("AUTH_COOKIE_HTTP_ONLY", True),
        "secure": sj.get("AUTH_COOKIE_SECURE", not settings.DEBUG),
        "samesite": sj.get("AUTH_COOKIE_SAMESITE", "Lax"),
        "path": "/",
    }


def set_auth_cookies(response, *, access=None, refresh=None):
    """Write access/refresh cookies using lifetimes from SIMPLE_JWT (the ONLY source)."""
    sj = settings.SIMPLE_JWT
    if access is not None:
        response.set_cookie(
            sj["AUTH_COOKIE"], access,
            max_age=sj.get("AUTH_COOKIE_ACCESS_MAX_AGE", 300), **_opts(),
        )
    if refresh is not None:
        response.set_cookie(
            sj["AUTH_COOKIE_REFRESH"], refresh,
            max_age=sj.get("AUTH_COOKIE_REFRESH_MAX_AGE", 86400), **_opts(),
        )
    # Non-httpOnly hint so the frontend can cheaply detect "logged in" state.
    response.set_cookie(
        "auth_state", "authenticated",
        max_age=sj.get("AUTH_COOKIE_REFRESH_MAX_AGE", 86400),
        **{k: v for k, v in _opts().items()} | {"httponly": False},
    )


def clear_auth_cookies(response):
    for name in ("auth_state", "access_token", "refresh_token", "csrftoken"):
        response.delete_cookie(name, path="/")
```

### 7.3 Login view (`accounts/api/views/auth_views.py`)

The login view validates input, blocks inactive accounts **without leaking whether the
email exists**, increments login bookkeeping, and sets cookies via the helper.

```python
@method_decorator([ensure_csrf_cookie], name="dispatch")
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    # RECOMMENDED: add `throttle_scope = "login"` to use the "login" rate (30/min dev,
    # 10/min prod). The current view does NOT set this yet — add it as a hardening step.

    def post(self, request, *args, **kwargs):
        if not request.data.get("email") or not request.data.get("password"):
            return Response({"message": "Email and password are required.",
                             "code": "required_fields_missing", "status": "error"},
                            status=status.HTTP_400_BAD_REQUEST)

        # Block inactive accounts; stay silent if the user doesn't exist (no enumeration).
        try:
            user = User.objects.get(email=request.data["email"])
            if not user.is_active:
                return Response({"message": "Account is inactive. Please contact support.",
                                 "code": "account_inactive", "status": "error"},
                                status=status.HTTP_403_FORBIDDEN)
        except User.DoesNotExist:
            pass

        try:
            serializer = self.get_serializer(data=request.data)
            if not serializer.is_valid():
                return Response({"message": "Authentication failed. Please check your credentials.",
                                 "code": "authentication_failed", "status": "error"},
                                status=status.HTTP_401_UNAUTHORIZED)

            data = serializer.validated_data
            user = serializer.user
            user.login_count += 1
            user.last_active = timezone.now()
            user.save(update_fields=["login_count", "last_active"])

            response = Response({"message": "Login successful", "status": "success",
                                 "data": self._build_login_response(user, data)},
                                status=status.HTTP_200_OK)
            set_auth_cookies(response, access=data["access"], refresh=data["refresh"])
            logger.info("Successful login: %s (role=%s)", user.email, user.role)
            return response
        except AuthenticationFailed:
            return Response({"message": "Invalid email or password.",
                             "code": "invalid_credentials", "status": "error"},
                            status=status.HTTP_401_UNAUTHORIZED)
```

> **Recommended hardening:** add `throttle_scope = "login"` to this view so it uses
> `DEFAULT_THROTTLE_RATES["login"]` (30/min dev, **10/min prod**) — your first line of
> defense against credential stuffing. The current view inherits `TokenObtainPairView`'s
> default throttling and does **not** set this scope yet.

### 7.4 Refresh view

```python
class CustomTokenRefreshView(TokenRefreshView):
    serializer_class = CustomTokenRefreshSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)  # validates + rotates
        # ROTATE_REFRESH_TOKENS=True → response carries a NEW refresh token.
        set_auth_cookies(
            response,
            access=response.data.get("access"),
            refresh=response.data.get("refresh"),
        )
        return response
```

### 7.5 Logout view

```python
class LogoutView(APIView):
    permission_classes = [AllowAny]   # logout must work even with an expired access token

    def post(self, request):
        refresh_token = request.data.get("refresh") or request.data.get("refresh_token")
        all_devices = request.data.get("all_devices", False)

        try:
            if refresh_token:
                token = RefreshToken(refresh_token)
                # Reject cross-user logout attempts.
                if (request.user.is_authenticated
                        and token.payload.get("user_id") != request.user.id):
                    return self._done("Invalid token, but logged out", "token_mismatch")
                token.blacklist()                       # explicit revocation
                if all_devices and request.user.is_authenticated:
                    OutstandingToken.objects.filter(user=request.user).delete()
        except Exception:
            pass  # Always clear cookies, even on a bad/expired token.

        return self._done("Successfully logged out", "logout_success")

    def _done(self, message, code):
        response = Response({"message": message, "code": code, "status": "success"},
                            status=status.HTTP_200_OK)
        clear_auth_cookies(response)
        return response
```

> **Why `token.blacklist()` and not auto-blacklist-on-rotation?** With
> `BLACKLIST_AFTER_ROTATION=False`, rotation never blacklists — that's what avoids the
> parallel-refresh race. Logout is the *one* place we deliberately revoke, so it's explicit
> and auditable. `all_devices=True` nukes every outstanding token for the user.

---

## 8. Token Flows

### Login

```
POST /api/v1/accounts/auth/login/
Body: { "email": "user@example.com", "password": "secret" }
Response 200: {
  "message": "Login successful",
  "status": "success",
  "data": {
    "tokens": { "access": "eyJ...", "refresh": "eyJ..." },
    "user": { "id", "email", "first_name", "last_name", "full_name", "role",
              "status", "email_verified", "profile_completion": {…} },
    "navigation": { "dashboard_route": "/dashboard", "next_action": "verify_email" }
  }
}
Set-Cookie: access_token (HttpOnly), refresh_token (HttpOnly), auth_state
```

The BFF reads `data.tokens.access`/`refresh` from the **body** and sets its *own* cookies.
Django's cookies are only for direct (Swagger/admin) access.

### Refresh

```
POST /api/v1/accounts/auth/refresh/
Body: { "refresh": "eyJ..." }       # optional — falls back to refresh_token cookie
Response 200: { "access": "eyJ...", "refresh": "eyJ..." }   # rotation → new refresh
Set-Cookie: access_token, refresh_token (both updated)
```

### Logout

```
POST /api/v1/accounts/auth/logout/
Body: { "refresh": "eyJ..." }       # or "all_devices": true
Response 200: { "message": "...", "code": "logout_success", "status": "success" }
Set-Cookie: all auth cookies cleared
```

### Token Verification

```
POST /api/v1/accounts/auth/verify/
Body: { "token": "eyJ..." }
Response: 200 OK (empty) if valid · 401 if invalid/expired
```

### Registration

```
POST /api/v1/accounts/auth/register/
Body: { "email", "password1", "password2", "first_name", "last_name", "role"? }
Response 201: { "user": {…}, "tokens": { "access", "refresh" }, "next_steps": [...] }
```

`RegisterView` is `@transaction.atomic`, throttled with `AnonRateThrottle`, and auto-logs
the user in by minting `RefreshToken.for_user(user)`. Username is auto-generated when omitted.

### Password Reset

```
POST /api/v1/accounts/auth/password/reset/
Body: { "email": "user@example.com" }
Response 200: { "message": "Password reset email sent", "status": "success" }
```
Django generates a one-time reset token (via `default_token_generator`) and sends an email
with a reset link containing `uid` + `token`. Always return 200 even if the email doesn't
exist (no user enumeration).

```
POST /api/v1/accounts/auth/password/reset/confirm/
Body: { "uid": "<base64 user id>", "token": "<reset token>", "new_password": "...", "new_password_confirm": "..." }
Response 200: { "message": "Password reset successful", "status": "success" }
Error 400: { "message": "...", "code": "invalid_token", "status": "error" }  # expired/used token
```

### Password Change (authenticated)

```
POST /api/v1/accounts/auth/password/change/
Headers: Authorization: Bearer <access>
Body: { "old_password": "...", "new_password": "...", "new_password_confirm": "..." }
Response 200: { "message": "Password changed successfully", "status": "success" }
Error 400: { "message": "...", "errors": { "new_password": ["…"] }, "status": "error" }
```
Requires a valid access token. `new_password` is run through Django's `validate_password`.
After a successful change, the user's existing tokens remain valid (no auto-revocation) —
consider blacklisting outstanding tokens if you want to force re-login on all devices.

### Email Verification

```
GET  /api/v1/accounts/auth/email/verify/?uid=<uid>&token=<token>
POST /api/v1/accounts/auth/email/verify/   Body: { "uid": "...", "token": "..." }
Response 200: { "message": "Email verified successfully", "status": "success" }
Error 400: { "message": "Invalid or expired token", "status": "error" }
```
Uses `default_token_generator` to verify the uid+token pair. On success, sets
`user.email_verified = True`.

### CSRF Token

```
GET  /api/v1/accounts/auth/csrf/
Response 200: { "message": "CSRF cookie set successfully", "csrfToken": "...", "status": "success" }
Set-Cookie: csrftoken
```
Only needed for the cookie-fallback flow (Swagger/admin). The BFF header-based flow does
not need CSRF tokens.

### Error response contract

All custom auth views return a **consistent error envelope** (not DRF's default
`{"detail": "…"}`):

```json
{
  "message": "Human-readable error",
  "code": "machine_code",
  "status": "error",
  "errors": { "field": ["…"] }
}
```

| Scenario | HTTP | `code` |
|---|---|---|
| Missing email/password | 400 | `required_fields_missing` |
| Bad credentials | 401 | `authentication_failed` / `invalid_credentials` |
| Inactive account | 403 | `account_inactive` |
| Validation error (register) | 400 | `validation_error` |
| Email already exists | 400 | `email_already_exists` |
| Throttled | 429 | — (DRF default `{"detail": "Request was throttled…"}`) |
| Expired/invalid refresh | 401 | — (SimpleJWT default `{"detail": "Token is invalid…"}`) |

> **No user enumeration:** login returns the same error for "no such user" and "wrong
> password". Password reset always returns 200 even if the email doesn't exist.

---

## 9. Google OAuth (Gold-Standard Implementation)

> **Goal:** "Sign in with Google" that fits the BFF cleanly and keeps **Django the identity
> authority** — Google proves *who* the user is; Django still mints *our* JWT pair so the
> rest of the system never special-cases social users.

### 9.1 Recommended flow — ID-token verification with `google-auth` (primary)

This is the cleanest and most secure path for a Next.js + DRF + JWT stack.

```
┌─────────┐  1. Google Sign-In button (Google Identity Services)
│ Browser │ ───────────────────────────────────────────────► Google
└────┬────┘  2. Google returns a signed ID token (JWT) to the browser
     │ 3. POST /api/auth/social/google  { id_token }   (to the Next.js BFF)
     ▼
┌─────────────┐ 4. BFF forwards → Django POST /accounts/auth/social/google/
│  Next.js BFF│
└──────┬──────┘
       ▼
┌──────────────────────────────────────────────────────────────────┐
│ Django GoogleLoginView:                                           │
│   5. google-auth verifies the ID token signature + audience       │
│   6. get_or_create user by verified email                         │
│   7. mint OUR SimpleJWT pair → return { tokens, user }            │
└──────────────────────────────────────────────────────────────────┘
       │ 8. BFF sets httpOnly cookies (same as password login)
       ▼  User is now logged in with OUR tokens.
```

**Why ID-token verification over the code flow?**
- The browser never hands an authorization *code* to your server; Google's library checks
  a cryptographically signed token offline against Google's public keys.
- No `client_secret` round-trip to Google from a user-facing request.
- One small endpoint, no redirect dance, no allauth routing — perfect behind a BFF.

**Add the library:**

```text
# backend/requirements.txt
google-auth==2.41.1
```

**Settings:**

```python
# config/settings/base.py
GOOGLE_OAUTH_CLIENT_ID = config("GOOGLE_OAUTH_CLIENT_ID", default="")
```

**Serializer + view (`accounts/api/views/auth_social_views.py`):**

```python
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status, serializers
from django.conf import settings
from django.db import transaction
from django.contrib.auth import get_user_model
from accounts.services.cookies import set_auth_cookies

User = get_user_model()


class GoogleAuthSerializer(serializers.Serializer):
    id_token = serializers.CharField()


class GoogleLoginView(APIView):
    """Verify a Google ID token and issue our own SimpleJWT pair."""

    permission_classes = [AllowAny]
    throttle_scope = "login"

    @transaction.atomic
    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # 1. Verify the ID token against Google's public keys + our client_id (audience).
        try:
            claims = google_id_token.verify_oauth2_token(
                serializer.validated_data["id_token"],
                google_requests.Request(),
                settings.GOOGLE_OAUTH_CLIENT_ID,
            )
        except ValueError:
            return Response(
                {"message": "Invalid Google token.", "code": "invalid_google_token",
                 "status": "error"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # 2. Google guarantees `email_verified` for verified accounts — require it.
        if not claims.get("email_verified"):
            return Response(
                {"message": "Google account email is not verified.",
                 "code": "email_unverified", "status": "error"},
                status=status.HTTP_403_FORBIDDEN,
            )

        email = claims["email"].lower()

        # 3. get_or_create — OAuth users are normal users with an unusable password.
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "username": email.split("@")[0],
                "first_name": claims.get("given_name", ""),
                "last_name": claims.get("family_name", ""),
                "email_verified": True,
            },
        )
        if created:
            user.set_unusable_password()

        # 4. Record the linked provider (idempotent).
        providers = user.social_auth_providers or {"active_providers": [], "connections": {}}
        if "google" not in providers["active_providers"]:
            providers["active_providers"].append("google")
        providers["connections"]["google"] = {"sub": claims["sub"]}
        user.social_auth_providers = providers
        user.login_count += 1
        user.update_last_active(save=False)
        user.save()

        # 5. Mint OUR tokens — identical shape to password login.
        refresh = RefreshToken.for_user(user)
        access = str(refresh.access_token)
        response = Response(
            {
                "message": "Login successful", "status": "success",
                "data": {
                    "tokens": {"access": access, "refresh": str(refresh)},
                    "user": {
                        "id": user.id, "email": user.email,
                        "full_name": user.full_name, "role": user.role,
                        "email_verified": user.email_verified,
                    },
                    "created": created,
                },
            },
            status=status.HTTP_200_OK,
        )
        set_auth_cookies(response, access=access, refresh=str(refresh))
        return response
```

**Wire it up (`accounts/api/urls.py`):**

```python
path("auth/social/google/", GoogleLoginView.as_view(), name="auth_social_google"),
```

**Frontend BFF (`app/api/auth/social/google/route.js`):** the BFF forwards the `id_token`
to Django, then sets cookies from `data.tokens` — exactly like the password login route in
the [frontend playbook](../../frontend/docs/AUTHENTICATION_PLAYBOOK.md). The browser obtains
the `id_token` from Google Identity Services (the `@react-oauth/google` `<GoogleLogin>`
component or the `google.accounts.id` script).

> 🔒 **Always verify `aud` (audience) = your client ID.** `verify_oauth2_token`'s third
> argument enforces this — without it, a token minted for *another* app would be accepted.
> Also enforce `email_verified` so you never trust an unverified Google email.

### 9.2 Authorization-code flow (already scaffolded)

The repo already ships a manual code-exchange utility at
`backend/apps/accounts/utils/oauth.py` (`get_google_user_info` / `get_github_user_info`)
plus a `SocialAuthSerializer(provider, code, redirect_uri)`. Use this when you need a
provider that doesn't issue front-channel ID tokens (e.g. **GitHub**): the BFF sends the
`code`, Django exchanges it server-side for the user profile, then mints our JWTs exactly
as in 9.1. Keep `client_secret` in Django settings — never expose it to the browser.

### 9.3 Enterprise alternative — `django-allauth` headless

`django-allauth` (65.18.0) is **already installed** (`allauth`, `allauth.account`,
`allauth.socialaccount` in `INSTALLED_APPS`; its backend in `AUTHENTICATION_BACKENDS`) but
its URLs are **not routed**. allauth 65's **headless API** is purpose-built for SPA/Next.js
and supports many providers, email verification, and account linking out of the box. Adopt
it when you need *several* providers or allauth's account-management surface; for a single
"Sign in with Google", the lean endpoint in 9.1 is less machinery to own. If you go this
route, add `dj-rest-auth` or use allauth headless endpoints and still exchange the result
for SimpleJWT so the rest of the API is unchanged.

| Approach | Best when | Cost |
|---|---|---|
| **9.1 `google-auth` ID token** *(recommended)* | One/few providers, BFF, want minimal surface | Write one small view |
| **9.2 code flow util** | Providers without front-channel ID tokens (GitHub) | Already in repo |
| **9.3 allauth headless** | Many providers, account linking, email flows | More config + routing |

---

## 10. Access Patterns (web / mobile / Swagger)

The same endpoints and tokens serve three clients:

### Web — BFF Proxy (production)

```
Browser → Next.js /api/proxy/* → reads httpOnly cookie →
          injects Authorization: Bearer <token> → Django (header auth)
```

Django only ever sees a Bearer header. The BFF owns all cookie management.

### Mobile — React Native

```
App → POST /accounts/auth/login/ → { data: { tokens } } in body →
      store in iOS Keychain / Android Keystore →
      send Authorization: Bearer <token> on every request
```

No cookies. Same endpoints, same tokens, zero mobile-specific backend config.

### Swagger / Admin — cookie fallback

```
Browser → /accounts/auth/login/ → httpOnly cookies set →
          browser auto-sends cookies → CustomJWTCookieAuthentication reads access_token
```

This is the *only* path that uses the cookie auth class — and the only one where CSRF is
enforced.

---

## 11. Known Issues & Required Hardening Fixes

> ⚠️ **Fix these before calling the system "flawless."** Found during this review.

### 11.1 Cookie max-age inconsistency (must fix)

The current `CustomTokenObtainPairView._set_auth_cookies` **hardcodes** lifetimes that
contradict both `SIMPLE_JWT` and the refresh view:

```python
# CURRENT (buggy): login view
response.set_cookie("refresh_token", ..., max_age=7 * 24 * 60 * 60)  # 7 days ❌
response.set_cookie("access_token",  ..., max_age=60 * 60)           # 1 hour ❌
# But SIMPLE_JWT says access=5min, refresh=1day, and the refresh view uses those values.
```

**Impact:** the access cookie outlives the JWT by 55 minutes (stale cookie carries a dead
token), and the refresh cookie lives 6 days past the refresh token's actual validity.

**Fix:** delete `_set_auth_cookies` and call the shared `set_auth_cookies` helper from
[Section 7.2](#72-cookie-helper-single-source-of-truth), which reads lifetimes from
`SIMPLE_JWT`. One source of truth → the bug becomes structurally impossible.

### 11.2 `SameSite` for cross-site deploys

`Lax` is correct when the frontend and API share a site (e.g. `app.example.com` +
`api.example.com` under `example.com`). If they're on **different sites**, cookie-based
flows need `SameSite=None; Secure`. The BFF/mobile header flow is unaffected — prefer it.

### 11.3 Production secret & algorithm

`SIGNING_KEY` falls back to a dev default in base settings. In production it **must** come
from the environment (`DJANGO_SECRET_KEY`) with no default. For multi-service token
verification, consider migrating HS256 → RS256 (asymmetric) so verifiers hold only the
public key.

---

| File | Purpose |
|------|---------|
| `config/settings/base.py` | Default `SIMPLE_JWT` config, DRF auth classes |
| `config/settings/development.py` | Dev overrides: enables cookie auth, CORS for localhost:3000 |
| `config/settings/production.py` | Production hardening: secure cookies, HSTS, throttling |
| `accounts/services/auth.py` | `CustomJWTCookieAuthentication` — cookie fallback for JWT |
## 12. Key Files

| File | Purpose |
|------|---------|
| `config/settings/base.py` | Default `SIMPLE_JWT` config, DRF auth/throttle classes |
| `config/settings/development.py` | Dev overrides: cookie auth class, CORS for localhost:3000, OAuth ids |
| `config/settings/production.py` | Hardening: secure cookies, HSTS, tightened throttling |
| `accounts/services/auth.py` | `CustomJWTCookieAuthentication` — cookie fallback + CSRF |
| `accounts/services/cookies.py` | **(recommended)** `set_auth_cookies` / `clear_auth_cookies` helpers |
| `accounts/api/views/auth_views.py` | Login, Logout, Refresh views |
| `accounts/api/views/auth_register_views.py` | Register, CSRF views |
| `accounts/api/views/auth_password_reset_views.py` | Password reset, email verification, password change |
| `accounts/api/views/auth_social_views.py` | **(Section 9)** `GoogleLoginView` |
| `accounts/api/serializers/auth_serializers.py` | Token serializers (user bundle + cookie refresh) |
| `accounts/utils/oauth.py` | Code-flow exchange util for Google/GitHub (Section 9.2) |
| `accounts/api/urls.py` | All auth endpoint URL registrations |
| `accounts/spectacular_extensions.py` | OpenAPI schema for cookie-based JWT |

---

## 13. Security Model & Threat Mitigations

| Threat | Mitigation in this design |
|---|---|
| **XSS stealing tokens** | Tokens live in `httpOnly` cookies (web) or Keychain (mobile); JS never reads them. |
| **CSRF on cookie flow** | `CustomJWTCookieAuthentication.enforce_csrf` + `SameSite=Lax`; header flow is immune. |
| **Token replay after leak** | 5-min access TTL + refresh rotation; logout blacklists; `all_devices` purge. |
| **Credential stuffing / brute force** | `login` throttle scope (10/min prod) + generic error messages. |
| **User enumeration** | Login returns the same error for "no such user" and "wrong password"; inactive check stays silent on non-existent users. |
| **Stolen refresh token** | Rotation means a stolen-then-used token is replaced; the legit client's next refresh fails → detectable. Short refresh TTL caps exposure. |
| **OAuth token forgery** | `google-auth` verifies signature **and** audience (`client_id`); `email_verified` required. |
| **Transport interception** | `SECURE_SSL_REDIRECT`, HSTS, and `Secure` cookies in production. |
| **Privilege escalation** | `IsAuthenticated` default (closed-by-default); `role` checks; viewset querysets scope non-admins to `self`. |

---

## 14. Testing Strategy

Tests live in `backend/apps/accounts/tests/` and protect the auth contract.

| Test File | Protects |
|---|---|
| `test_auth_views.py` | Login (success, cookie `HttpOnly`, wrong password, missing fields, inactive), refresh + rotation, verify, logout + blacklist + multi-device, register, CSRF, password reset/change, email verify |
| `test_serializers.py` | User serializers, `PasswordChangeSerializer` validation |
| `test_models.py` | `CustomUser` defaults, roles, email/username uniqueness, `full_name`, `verify_email()`, `update_last_active()` |
| `test_api_viewsets.py` | `CustomUserViewSet` CRUD + permission scoping (admin sees all, user sees self), `me`, `stats` |

**When you add the Google endpoint (Section 9), add `test_auth_social_views.py`** covering:
valid ID token → user created + tokens issued; invalid token → 401; unverified email → 403;
existing user → linked, not duplicated; audience mismatch → 401. Mock
`google.oauth2.id_token.verify_oauth2_token` so tests never hit Google.

```bash
# All accounts tests
python manage.py test accounts.tests --settings=config.settings.test -v 2

# Fast re-run (reuse DB)
python manage.py test accounts.tests --settings=config.settings.test -v 2 --keepdb

# Validate + export the OpenAPI schema
python manage.py spectacular --validate --settings=config.settings.development
python manage.py spectacular --file schema.yml --settings=config.settings.development
```

---

## 15. Operational Workflow / Runbook

### 15.1 Local setup

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                      # set DJANGO_SECRET_KEY, DB, GOOGLE_OAUTH_CLIENT_ID
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver                # http://localhost:8000
# Swagger UI: http://localhost:8000/api/v1/schema/swagger-ui/
```

### 15.2 Smoke-test the auth flow with curl

```bash
BASE=http://localhost:8000/api/v1/accounts

# 1. Login
curl -i -c jar.txt -X POST $BASE/auth/login/ \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@aparsoft.com","password":"test123"}'

# 2. Call a protected endpoint with the cookie (cookie-auth path)
curl -s -b jar.txt $BASE/users/me/ | jq

# 3. Refresh (reads refresh_token cookie)
curl -i -b jar.txt -c jar.txt -X POST $BASE/auth/refresh/

# 4. Logout (blacklists + clears cookies)
curl -i -b jar.txt -X POST $BASE/auth/logout/
```

### 15.3 Adding a new protected endpoint

1. Default is `IsAuthenticated` — you get auth for free. Add `permission_classes` only to
   *widen* (`AllowAny`) or *narrow* (custom role check) access.
2. Scope querysets so non-admins only see their own rows (mirror `CustomUserViewSet`).
3. Add a throttle scope for sensitive write endpoints.
4. Write the test first (contract), then the view.

### 15.4 Configuring Google OAuth (Section 9)

1. Create an OAuth 2.0 Client ID in Google Cloud Console (type: Web application).
2. Add the frontend origin to **Authorized JavaScript origins** and the BFF callback to
   **Authorized redirect URIs** (only needed for the code flow).
3. Put the client ID in `GOOGLE_OAUTH_CLIENT_ID` (backend) and the public client ID in the
   frontend env. Keep the **client secret** server-side only.
4. `pip install google-auth==2.41.1`, add `GoogleLoginView`, wire the URL, add tests.

### 15.5 Token/secret rotation

- Rotating `DJANGO_SECRET_KEY` invalidates **all** existing JWTs (everyone re-logs in).
  Schedule it during low traffic; communicate forced logout.
- To force-logout one user: delete their `OutstandingToken` rows (admin) or call logout
  with `all_devices: true`.

---

## 16. Production Checklist

- [ ] `DJANGO_SECRET_KEY` is a strong random value from env (no dev default) · `DEBUG = False`
- [ ] `ALLOWED_HOSTS` set to the real domain(s)
- [ ] `CORS_ALLOWED_ORIGINS` + `CSRF_TRUSTED_ORIGINS` = production frontend origin only
- [ ] `SECURE_SSL_REDIRECT = True`, HSTS enabled (`SECURE_HSTS_SECONDS` ≥ 1 year)
- [ ] `AUTH_COOKIE_SECURE = SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True`
- [ ] **Cookie max-age inconsistency fixed** (Section 11.1) — login uses `set_auth_cookies`
- [ ] Throttling tightened (login: 10/min, anon: 50/min)
- [ ] Database SSL enabled (`sslmode: require`)
- [ ] Token blacklist app migrated; periodic flush of expired blacklisted tokens scheduled
- [ ] If Google OAuth is live: `GOOGLE_OAUTH_CLIENT_ID` set, audience verification tested
- [ ] `python manage.py spectacular --validate` passes; auth tests green

---

## 17. Reference

- [SimpleJWT settings](https://django-rest-framework-simplejwt.readthedocs.io/en/latest/settings.html) · [SimpleJWT GitHub](https://github.com/jazzband/djangorestframework-simplejwt)
- [google-auth — verifying Google ID tokens](https://google-auth.readthedocs.io/en/master/reference/google.oauth2.id_token.html)
- [Google Identity Services (frontend)](https://developers.google.com/identity/gsi/web/guides/overview)
- [django-allauth headless](https://docs.allauth.org/en/latest/headless/index.html) · [dj-rest-auth](https://dj-rest-auth.readthedocs.io/)
- [DRF throttling](https://www.django-rest-framework.org/api-guide/throttling/) · [OWASP ASVS — Authentication](https://owasp.org/www-project-application-security-verification-standard/)
- [Frontend Auth Playbook](../../frontend/docs/AUTHENTICATION_PLAYBOOK.md) — the BFF proxy that consumes these endpoints

---

That is the complete, gold-standard backend auth reference: principles, exact code, the
Google OAuth path, the known fixes, and the runbook. Implement Sections 7.2 + 11.1 and add
Section 9, and this backend is production-grade, secure, and world-class.
