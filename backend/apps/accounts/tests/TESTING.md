# Accounts App — Django Test Suite

> Location: `backend/apps/accounts/tests/`
> Settings: `config.settings.test`
> Database: PostgreSQL test runner (default test DB)

---

## Quick start

Run from the repository backend folder:

```bash
cd backend
source venv/bin/activate

# Run the full accounts test suite (99 tests)
python manage.py test accounts.tests --settings=config.settings.test -v 2

# Run one module
python manage.py test accounts.tests.test_auth_views --settings=config.settings.test -v 2
python manage.py test accounts.tests.test_models --settings=config.settings.test -v 2

# Run one test class
python manage.py test accounts.tests.test_auth_views.LoginViewTests --settings=config.settings.test -v 2

# Run one test method
python manage.py test accounts.tests.test_auth_views.LoginViewTests.test_login_success --settings=config.settings.test -v 2

# Fast re-run (reuses test DB)
python manage.py test accounts.tests --settings=config.settings.test -v 2 --keepdb
```

---

## Test files

| File | Tests | Description |
|------|------:|-------------|
| `_mixins.py` | — | Shared `AccountsTestMixin` with factory helpers for users and contacts |
| `test_auth_views.py` | 42 | Login, refresh, verify, logout, register, CSRF, password change, Bearer auth, full lifecycle |
| `test_api_viewsets.py` | 27 | ViewSet CRUD, actions (/me, /verify-email, /change-password, /profile-image, /stats), permissions, swagger_fake_view guard |
| `test_models.py` | 18 | CustomUser creation, email uniqueness, verify_email(), full_name, UserContact signal/OneToOne |
| `test_serializers.py` | 12 | Serializer validation: create (password, email dup), update (partial, email dedup), read (nested contact) |
| **Total** | **99** | |

---

## Test infrastructure

### `AccountsTestMixin` (`_mixins.py`)

Shared factory methods used across all test files:

| Method | Purpose |
|--------|---------|
| `create_user(role)` | User with unique username/email and given role (password: `"testpass123!"`) |
| `create_admin_user()` | User with role='admin' |
| `create_superuser()` | Staff + superuser with role='admin' |
| `get_user_contact(user)` | Retrieve the signal-created UserContact |
| `update_user_contact(user, **kwargs)` | Update the signal-created contact |
| `get_default_country()` | Returns or creates Country(pk=1) |

---

## How to Write Auth Tests

### Pattern: Mixin + TestCase

```python
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from . import AccountsTestMixin

LOGIN_URL = "/api/v1/accounts/auth/login/"

class MyTests(AccountsTestMixin, TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = self.create_user()

    def test_something(self):
        self.client.force_authenticate(self.user)
        resp = self.client.get("/api/v1/accounts/users/me/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
```

### Response Structures

**Login response** — tokens are nested inside `data`:
```python
resp.data["data"]["tokens"]["access"]
resp.data["data"]["tokens"]["refresh"]
resp.data["data"]["user"]["email"]
```

**Register response** — tokens are at top level:
```python
resp.data["tokens"]["access"]
resp.data["tokens"]["refresh"]
resp.data["user"]["email"]
```

**CSRF endpoint** — returns `JsonResponse`, use `.json()`:
```python
resp = self.client.get(CSRF_URL)
data = resp.json()
```

**Paginated list responses:**
```python
resp.data["results"]  # The list of items
```

### Key Gotchas

- User passwords are always `"testpass123!"` (set in `_mixins.py`)
- `post_save` signal auto-creates `UserContact` — never create contacts manually
- Use `force_authenticate(user)` for API tests, not login flows
- Auth view tests cover the actual login/register flows via HTTP

---

## Auth Test Coverage by Endpoint

| Endpoint | Tests | Scenarios |
|----------|-------|-----------|
| `POST auth/login/` | 10 | Success, cookies (httpOnly), wrong password, missing fields, nonexistent user, login_count, last_active, user role |
| `POST auth/refresh/` | 7 | Body token, token rotation, cookies updated, cookie fallback, invalid/missing token, no-blacklist-after-rotation |
| `POST auth/verify/` | 3 | Valid token, invalid token, missing token |
| `POST auth/logout/` | 5 | Success, clears cookies, alt key name, invalid token (idempotent), no token |
| `POST auth/register/` | 6 | Success, duplicate email, password mismatch, missing fields, auto-creates contact, default role |
| `GET auth/csrf/` | 2 | Returns token, sets cookie |
| `POST auth/password/change/` | 4 | Success, wrong old password, too short, requires auth |
| Bearer auth | 3 | Grants access, no auth returns 401, invalid token |
| Integration | 2 | Full register→login→access→refresh→logout lifecycle, login→verify flow |

---

## Adding a New Auth Test

1. Open `test_auth_views.py`
2. Find the appropriate test class (or create a new one at the bottom)
3. Add your test method following the existing patterns
4. Run with `--keepdb` for speed:

```bash
python manage.py test accounts.tests.test_auth_views.MyNewClass --settings=config.settings.test -v 2 --keepdb
```

5. Update the test count in this file and in `backend/docs/current_status.md`

---

## Settings used during tests

| Setting | Value | Why |
|---------|-------|-----|
| `DJANGO_SETTINGS_MODULE` | `config.settings.test` | Extends development settings |
| `PASSWORD_HASHERS` | `[MD5PasswordHasher]` | ~100x faster than PBKDF2 |
| `CACHES` | `DummyCache` | No caching side effects |
| `CELERY_TASK_ALWAYS_EAGER` | `True` | Tasks run synchronously in test process |

---

## Rules

1. **No external calls.** Tests must not call LLMs, OCR providers, payment APIs, or production databases.
2. **Unique IDs.** The `_next_id()` counter in `_mixins.py` ensures uniqueness across `--keepdb` runs.
3. **Independent files.** Every test file is self-contained — you can run any file in isolation.
4. **Signal awareness.** The `post_save` signal on `CustomUser` auto-creates `UserContact`. Always use `get_user_contact()` / `update_user_contact()`.
