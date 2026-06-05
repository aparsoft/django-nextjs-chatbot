# Accounts App

> User authentication, registration, profile management, and JWT token lifecycle for the AI Chatbot platform.

---

## What This App Does

The `accounts` app is the **identity layer** of the platform. Every request flows through it — authentication, authorization, and user data all start here.

```
┌───────────────────────────────────────────────────────────┐
│                     accounts app                          │
│                                                           │
│  ┌────────────┐  ┌──────────────┐  ┌────────────────────┐ │
│  │  Models    │  │  Serializers │  │  Views / ViewSets  │ │
│  │            │  │              │  │                    │ │
│  │ CustomUser │  │ Auth (5)     │  │ Auth (6 endpoints) │ │
│  │ UserContact│  │ User (4)     │  │ User (8 endpoints) │ │
│  │            │  │ Contact (3)  │  │ Contact (4 CRUD)   │ │
│  └────────────┘  └──────────────┘  └────────────────────┘ │
│                                                           │
│  ┌───────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │  Signals  │  │  Services    │  │  Admin             │  │
│  │           │  │              │  │                    │  │
│  │ post_save │  │ CustomJWT    │  │ CustomUserAdmin    │  │
│  │ → Contact │  │ CookieAuth   │  │ UserContactAdmin   │  │
│  └───────────┘  └──────────────┘  └────────────────────┘  │
└───────────────────────────────────────────────────────────┘
```

---

## Quick Reference

### Models

| Model | Purpose | Key Detail |
|-------|---------|-----------|
| `CustomUser` | Auth + profile | Email-based login. Roles: user/admin. 8 indexes. |
| `UserContact` | Address + contact info | OneToOne to CustomUser. Auto-created via signal. |

→ Full model docs: [model_architecture.md](./model_architecture.md)

### Endpoints (21 total)

**Auth (6):**

| Method | URL | What It Does |
|--------|-----|-------------|
| POST | `auth/login/` | Login → JWT tokens + user profile + cookies |
| POST | `auth/refresh/` | Refresh → new access + rotated refresh token |
| POST | `auth/verify/` | Verify access token validity |
| POST | `auth/logout/` | Blacklist refresh + clear cookies |
| POST | `auth/register/` | Create account → auto-generate username |
| GET | `auth/csrf/` | Get CSRF token cookie |

**Password & Email (4):**

| Method | URL | What It Does |
|--------|-----|-------------|
| POST | `auth/password/reset/` | Request reset email |
| POST | `auth/password/reset/confirm/` | Confirm reset with uid+token |
| POST | `auth/password/change/` | Change password (authenticated) |
| GET/POST | `auth/email/verify/` | Verify email via uid+token |

**User CRUD (8):**

| Method | URL | What It Does |
|--------|-----|-------------|
| GET | `users/` | List users (admin: all, user: self) |
| POST | `users/` | Create user |
| GET | `users/{id}/` | Retrieve user |
| PATCH | `users/{id}/` | Update user |
| DELETE | `users/{id}/` | Delete user |
| GET | `users/me/` | Current user profile |
| POST | `users/{id}/verify-email/` | Admin verify email |
| GET | `users/stats/` | User statistics |

**Contact & Avatar (3):**

| Method | URL | What It Does |
|--------|-----|-------------|
| CRUD | `user-contacts/` | Contact info (auto-created with user) |
| GET/POST/DEL | `profile/avatar/` | Avatar upload (200x200, max 5MB) |

### Authentication Chain

```
Request → JWTAuthentication (header) → CustomJWTCookieAuthentication (cookie) → SessionAuthentication → BasicAuthentication
```

→ Full auth docs: [JWT Deep Dive](../../../local_folder/tutorials/01_overview/02_authentication_jwt_deep_dive.md)

---

## Directory Structure

```
accounts/
├── apps.py                          # AppConfig + signal registration
├── models/
│   ├── __init__.py                   # Exports CustomUser, UserContact
│   └── custom_user.py                # Both models (CustomUser + UserContact)
├── signals/
│   └── user_creation_signals.py      # post_save → auto-create UserContact
├── admin/
│   ├── __init__.py
│   └── user_admin.py                 # CustomUserAdmin + UserContactAdmin
├── api/
│   ├── urls.py                       # All 21 endpoint registrations
│   ├── views/
│   │   ├── auth_views.py             # Login, Logout, Refresh
│   │   ├── auth_register_views.py    # Register, CSRF
│   │   ├── auth_password_reset_views.py  # Password reset, email verify
│   │   ├── custom_user_views.py      # User CRUD + actions
│   │   └── profile_avatar_views.py   # Avatar upload/resize
│   └── serializers/
│       ├── auth_serializers.py       # Token + Register + PasswordChange
│       ├── custom_user_serializers.py # User CRUD serializers
│       └── response_serializers.py   # OpenAPI response schemas
├── services/
│   ├── __init__.py
│   └── auth.py                       # CustomJWTCookieAuthentication
├── utils/
│   ├── helper.py                     # Default JSON structures
│   ├── profile_picture_utils.py      # Avatar resize + migration safety
│   ├── oauth.py                      # Google & GitHub OAuth
│   └── types.py                      # SocialAuthConnection dataclass
├── spectacular_extensions.py         # OpenAPI cookie auth scheme
├── docs/
│   └── model_architecture.md         # This file's companion
└── tests/
    ├── test_models.py
    ├── test_api_viewsets.py
    └── _mixins.py                    # Test factories + helpers
```

---

## Key Patterns

### 1. Email-First Auth

```python
class CustomUser(AbstractUser):
    USERNAME_FIELD = "email"       # Login with email
    REQUIRED_FIELDS = ["username"]  # Username still required (admin needs it)
```

Username is auto-generated from name if omitted:
```python
# RegisterSerializer
base_username = slugify(f"{first_name} {last_name}")
# If taken: "ramsharmaa1b2c3"
# If still taken: "user_a1b2c3d4e5"
```

### 2. Signal-Guaranteed Contact Record

Every `CustomUser` gets a `UserContact` — no exceptions:

```python
@receiver(post_save, sender=CustomUser)
def create_user_contact(sender, instance, created, **kwargs):
    if created:
        UserContact.objects.create(user=instance, ...)
```

Access it via `user.contact` (the `related_name`).

### 3. Serializer Dispatch Per Action

One model, multiple serializers — each optimized for its job:

| Action | Serializer | Fields |
|--------|-----------|--------|
| `list` | `CustomUserListSerializer` | id, email, full_name, role, is_active |
| `create` | `CustomUserCreateSerializer` | email, password, first_name, last_name, role |
| `retrieve` | `CustomUserSerializer` | All fields + computed properties |
| `update` | `CustomUserUpdateSerializer` | first_name, last_name, profile_picture |

### 4. Cookie + Header Dual Auth

```python
class CustomJWTCookieAuthentication(JWTAuthentication):
    def authenticate(self, request):
        header = self.get_header(request)
        if header is None:
            # Fallback: read from cookie
            access_token = request.COOKIES.get("access_token")
            ...
```

Primary: `Authorization: Bearer <token>` (BFF proxy, mobile).
Fallback: `access_token` cookie (Swagger, direct browser).

### 5. Avatar Pipeline

```
Upload → Validate (max 5MB, image/*) → Open resize (200x200, JPEG 85%) → Save to media/avatars/
```

---

## Dependencies

| Dependency | Purpose |
|-----------|---------|
| `djangorestframework-simplejwt` | JWT token generation + validation |
| `django-allauth` | Social auth integration |
| `Pillow` | Avatar image processing |
| `drf-spectacular` | OpenAPI schema generation |
| `django-cors-headers` | CORS middleware |
| `psycopg2` | PostgreSQL + GIN indexes for JSONFields |

---

## Related Docs

| Doc | Location |
|-----|----------|
| Model Architecture (full) | [`docs/model_architecture.md`](./model_architecture.md) |
| JWT Deep Dive | [`local_folder/tutorials/01_overview/02_authentication_jwt_deep_dive.md`](../../../local_folder/tutorials/01_overview/02_authentication_jwt_deep_dive.md) |
| Backend Auth | [`docs/AUTHENTICATION.md`](../../docs/AUTHENTICATION.md) |
| BFF Proxy Playbook | [`frontend/docs/AUTHENTICATION_PLAYBOOK.md`](../../../frontend/docs/AUTHENTICATION_PLAYBOOK.md) |