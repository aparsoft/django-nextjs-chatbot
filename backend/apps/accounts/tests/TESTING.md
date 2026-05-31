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

# Run the full accounts test suite
python manage.py test accounts.tests --settings=config.settings.test -v 2

# Run one module
python manage.py test accounts.tests.test_models --settings=config.settings.test -v 2

# Run one test class
python manage.py test accounts.tests.test_api_viewsets.CustomUserViewSetTests --settings=config.settings.test -v 2

# Run one test method
python manage.py test accounts.tests.test_api_viewsets.CustomUserViewSetTests.test_me_returns_current_user --settings=config.settings.test -v 2
```

> Use `--keepdb` for repeat runs. Drop it only when migrations or test database structure need rebuilding.

---

## Test files

| File | Tests | Description |
|------|------:|-------------|
| `_mixins.py` | — | Shared `AccountsTestMixin` with factory helpers for users and contacts |
| `test_models.py` | ~15 | CustomUser creation, email uniqueness, verify_email(), full_name, UserContact CRUD |
| `test_serializers.py` | ~15 | Serializer validation: create (password, email dup), update (partial, email dedup), read (nested contact) |
| `test_api_viewsets.py` | ~25 | ViewSet CRUD, actions (/me, /verify-email, /change-password, /profile-image, /stats), permissions, swagger_fake_view guard |
| **Total** | **~55** | |

---

## Test infrastructure

### `AccountsTestMixin` (`_mixins.py`)

Shared factory methods used across all test files:

| Method | Purpose |
|--------|---------|
| `create_user(role)` | User with unique username/email and given role |
| `create_admin_user()` | User with role='admin' |
| `create_superuser()` | Staff + superuser with role='admin' |
| `create_user_contact(user)` | UserContact with city/state/timezone |
| `get_default_country()` | Returns or creates Country(pk=1) |

---

## Adding new accounts tests

1. Create `tests/test_<feature>.py`.
2. Import `AccountsTestMixin` from `from . import AccountsTestMixin`.
3. Prefer `SimpleTestCase` for pure serializer/schema tests that don't need the database.
4. Use `TestCase` for model persistence or API database behavior.
5. Keep external services mocked; tests must not call LLMs, OCR providers, payment APIs, or production databases.
6. Add the new module and test count to the table above.

---

## Settings used during tests

| Setting | Value |
|---------|-------|
| `DJANGO_SETTINGS_MODULE` | `config.settings.test` |
| `CELERY_TASK_ALWAYS_EAGER` | `True` (inherited from base) |
| `CELERY_BROKER_URL` | `memory://` (inherited from base) |
