# Authentication — Django Backend Implementation

> How authentication works on the Django backend, what endpoints exist, what settings govern them, and how the frontend BFF proxy integrates.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                     Next.js BFF Proxy                        │
│  (manages httpOnly cookies, handles refresh lock)            │
│                                                              │
│  Login:     POST /api/auth/login   → Django /auth/login/    │
│  Refresh:   POST /api/auth/refresh → Django /auth/refresh/  │
│  Logout:    POST /api/auth/logout  → Django /auth/logout/   │
│  API calls: GET  /api/proxy/...    → Django /api/v1/...     │
│              (reads cookie → injects Bearer header)          │
└──────────────────────────┬───────────────────────────────────┘
                           │  Authorization: Bearer <JWT>
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                     Django Backend                           │
│                                                              │
│  SimpleJWT generates + validates tokens                      │
│  CustomJWTCookieAuthentication reads cookies as fallback     │
│  Token blacklist for explicit logout                         │
│                                                              │
│  Django does NOT know about the BFF proxy.                   │
│  It sees standard JWT Bearer requests.                       │
│  Mobile app (React Native) talks directly to same endpoints. │
└──────────────────────────────────────────────────────────────┘
```

---

## Authentication Classes

Django accepts tokens via two mechanisms (in priority order):

| Priority | Class | How It Works |
|----------|-------|-------------|
| 1 | `JWTAuthentication` | Reads `Authorization: Bearer <token>` header. **Primary method** — used by BFF proxy and mobile app. |
| 2 | `CustomJWTCookieAuthentication` | Falls back to `access_token` cookie if no header. Used for Swagger UI, admin, and direct browser testing. |
| 3 | `SessionAuthentication` | Django admin session. |
| 4 | `BasicAuthentication` | Fallback for simple testing. |

---

## API Endpoints

All endpoints are at `/api/v1/accounts/`.

### Token Endpoints

| Method | URL | View | Auth | Purpose |
|--------|-----|------|------|---------|
| POST | `auth/login/` | `CustomTokenObtainPairView` | AllowAny | Login → returns `{access, refresh, user}` + sets cookies |
| POST | `auth/refresh/` | `CustomTokenRefreshView` | AllowAny | Refresh → returns `{access, refresh?}` + updates cookies |
| POST | `auth/verify/` | `TokenVerifyView` | AllowAny | Verify access token is valid |
| POST | `auth/logout/` | `LogoutView` | AllowAny | Blacklist refresh token + clear cookies |

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

**Total: 21 endpoints**

---

## Token Configuration

### SimpleJWT Settings

```python
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=5),    # Short — BFF refreshes transparently
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),      # 24 hours
    "ROTATE_REFRESH_TOKENS": True,                     # New refresh token on every refresh
    "BLACKLIST_AFTER_ROTATION": False,                 # No race condition; logout blacklists explicitly
    "UPDATE_LAST_LOGIN": False,                        # Avoid DB write on every login
    "ALGORITHM": "HS256",
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    # Cookie settings (for direct API access — Swagger, admin)
    "AUTH_COOKIE": "access_token",
    "AUTH_COOKIE_REFRESH": "refresh_token",
    "AUTH_COOKIE_SECURE": False,     # True in production (HTTPS)
    "AUTH_COOKIE_HTTP_ONLY": True,
    "AUTH_COOKIE_SAMESITE": "Lax",
    "AUTH_COOKIE_ACCESS_MAX_AGE": 300,    # 5 minutes
    "AUTH_COOKIE_REFRESH_MAX_AGE": 86400, # 1 day
}
```

### Why These Values

| Setting | Value | Rationale |
|---------|-------|-----------|
| `ACCESS_TOKEN_LIFETIME` | 5 min | Short-lived = limited damage if compromised. BFF proxy refreshes transparently. |
| `REFRESH_TOKEN_LIFETIME` | 1 day | Balance between security and UX. Not too long (7 days was excessive). |
| `ROTATE_REFRESH_TOKENS` | True | New refresh token on every use limits replay attacks. |
| `BLACKLIST_AFTER_ROTATION` | False | Avoids race condition when parallel BFF requests hit refresh simultaneously. Logout still explicitly blacklists. |
| `UPDATE_LAST_LOGIN` | False | Avoids extra DB write on every token generation. `last_active` is updated separately in login view. |

---

## Token Flows

### Login

```
POST /api/v1/accounts/auth/login/
Body: { "email": "user@example.com", "password": "secret" }
Response: {
    "access": "eyJ...",
    "refresh": "eyJ...",
    "user": { "id", "email", "first_name", "last_name", "full_name", "role", "status", "email_verified" }
}
Cookies set: access_token, refresh_token, auth_state
```

The BFF proxy reads `access` and `refresh` from the response body and sets its own httpOnly cookies. Django's cookies are for direct API access.

### Refresh

```
POST /api/v1/accounts/auth/refresh/
Body: { "refresh": "eyJ..." }   # or reads from refresh_token cookie
Response: {
    "access": "eyJ...",          # new access token
    "refresh": "eyJ..."          # new refresh token (ROTATE_REFRESH_TOKENS=True)
}
Cookies updated: access_token, refresh_token
```

The `CustomTokenRefreshSerializer` accepts refresh token from either the request body or the `refresh_token` cookie.

### Logout

```
POST /api/v1/accounts/auth/logout/
Body: { "refresh": "eyJ..." }   # or "refresh_token" key, or "all_devices": true
Response: { "message": "...", "code": "...", "status": "success" }
Cookies cleared: auth_state, access_token, refresh_token, csrftoken
```

The refresh token is blacklisted via `token.blacklist()`. With `all_devices: true`, all `OutstandingToken` objects for the user are deleted.

### Token Verification

```
POST /api/v1/accounts/auth/verify/
Body: { "token": "eyJ..." }
Response: 200 OK (empty) if valid, 401 if invalid/expired
```

---

## Dual Access Patterns

The backend supports two access patterns simultaneously:

### 1. BFF Proxy (Primary — Production)

```
Browser → Next.js /api/proxy/* → reads httpOnly cookie →
          injects Authorization: Bearer <token> →
          Django receives standard header-based JWT request
```

Django only sees `Authorization: Bearer <token>`. The BFF handles all cookie management.

### 2. Direct API Access (Development / Swagger / Admin)

```
Browser → Django auth/login/ → sets httpOnly cookies →
          Browser sends cookies automatically →
          CustomJWTCookieAuthentication reads cookie from request
```

`CustomJWTCookieAuthentication` (defined in `accounts/services/auth.py`) extends `JWTAuthentication` with a cookie fallback: if no `Authorization` header is present, it reads `access_token` from `request.COOKIES`.

### 3. Mobile App (React Native)

```
App → POST Django /auth/login/ → receives { access, refresh } in body →
      Stores in iOS Keychain / Android Keystore →
      Sends Authorization: Bearer <token> on every request
```

No cookies involved. Same endpoints, same tokens. Django doesn't need special mobile configuration.

---

## Key Files

| File | Purpose |
|------|---------|
| `config/settings/base.py` | Default `SIMPLE_JWT` config, DRF auth classes |
| `config/settings/development.py` | Dev overrides: enables cookie auth, CORS for localhost:3000 |
| `config/settings/production.py` | Production hardening: secure cookies, HSTS, throttling |
| `accounts/services/auth.py` | `CustomJWTCookieAuthentication` — cookie fallback for JWT |
| `accounts/api/views/auth_views.py` | Login, Logout, Refresh views |
| `accounts/api/views/auth_register_views.py` | Register, CSRF views |
| `accounts/api/views/auth_password_reset_views.py` | Password reset, email verification, password change |
| `accounts/api/serializers/auth_serializers.py` | Token serializers with user data + cookie refresh |
| `accounts/api/urls.py` | All auth endpoint URL registrations |
| `accounts/spectacular_extensions.py` | OpenAPI schema for cookie-based JWT |

---

## Production Checklist

Before deploying to production:

- [ ] `DJANGO_SECRET_KEY` is a strong, random value (not the dev default)
- [ ] `ALLOWED_HOSTS` is set to actual domain(s)
- [ ] `CORS_ALLOWED_ORIGINS` is set to the production frontend URL only
- [ ] `CSRF_TRUSTED_ORIGINS` matches CORS origins
- [ ] `SECURE_SSL_REDIRECT = True` (enforce HTTPS)
- [ ] `AUTH_COOKIE_SECURE = True` (cookies only over HTTPS)
- [ ] `SESSION_COOKIE_SECURE = True`
- [ ] `CSRF_COOKIE_SECURE = True`
- [ ] Database SSL is enabled (`sslmode: require`)
- [ ] Throttling is production-appropriate (login: 10/min, anon: 50/min)
- [ ] `DEBUG = False`

---

## Running Auth Tests

```bash
# All accounts tests (57 tests)
python manage.py test accounts.tests --settings=config.settings.test -v 2

# Quick re-run with existing DB
python manage.py test accounts.tests --settings=config.settings.test -v 2 --keepdb

# Validate OpenAPI schema
python manage.py spectacular --validate --settings=config.settings.development

# Export schema
python manage.py spectacular --file schema.yml --settings=config.settings.development
```

---

## Reference

- [SimpleJWT Settings Documentation](https://django-rest-framework-simplejwt.readthedocs.io/en/latest/settings.html)
- [SimpleJWT GitHub](https://github.com/jazzband/djangorestframework-simplejwt)
- [Frontend Auth Playbook](../../frontend/docs/AUTHENTICATION_PLAYBOOK.md) — BFF proxy implementation plan
