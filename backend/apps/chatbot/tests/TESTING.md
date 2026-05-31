# Chatbot App — Django Test Suite

> Location: `backend/apps/chatbot/tests/`
> Settings: `config.settings.test`
> Database: PostgreSQL test runner (default test DB)

---

## Quick start

Run from the repository backend folder:

```bash
cd backend
source venv/bin/activate

# Run the full chatbot test suite
python manage.py test chatbot.tests --settings=config.settings.test -v 2

# Run one module
python manage.py test chatbot.tests.test_models --settings=config.settings.test -v 2
python manage.py test chatbot.tests.test_serializers --settings=config.settings.test -v 2
python manage.py test chatbot.tests.test_api_viewsets --settings=config.settings.test -v 2

# Run one test class
python manage.py test chatbot.tests.test_api_viewsets.ChatSessionViewSetCRUDTests --settings=config.settings.test -v 2

# Run one test method
python manage.py test chatbot.tests.test_api_viewsets.ChatSessionViewSetCRUDTests.test_create_session --settings=config.settings.test -v 2

# Fast re-run (reuses test DB)
python manage.py test chatbot.tests --settings=config.settings.test -v 2 --keepdb

# Run chatbot + accounts together
python manage.py test accounts.tests chatbot.tests --settings=config.settings.test -v 2 --keepdb
```

---

## Test files

| File | Tests | Description |
|------|------:|-------------|
| `_mixins.py` | — | Shared `ChatbotTestMixin` with factory helpers for all chatbot models |
| `test_models.py` | 58 | Model creation, properties, state transitions, class methods, constraints across all 8 models |
| `test_serializers.py` | 34 | Serializer validation: create, update, read, field checks for all 8 model serializer sets |
| `test_api_viewsets.py` | 55 | ViewSet CRUD, custom actions, permissions, swagger_fake_view guard for all 8 ViewSets |
| **Total** | **~147** | |

---

## Test infrastructure

### `ChatbotTestMixin` (`_mixins.py`)

Shared factory methods used across all test files:

| Method | Purpose |
|--------|---------|
| `create_user(role)` | User with unique username/email and given role (password: `"testpass123!"`) |
| `create_admin_user()` | User with role='admin' |
| `create_session(user)` | ChatSession for the user |
| `create_preference(user)` | UserPreference (get-or-create) |
| `create_token_usage(user, session)` | TokenUsage record with costs |
| `create_feedback(user, session)` | MessageFeedback record |
| `create_document(user, session)` | UserDocument record (no actual file) |
| `create_system_prompt()` | SystemPromptTemplate |
| `create_user_tool(user, tool_name)` | UserTool from TOOL_REGISTRY |
| `create_api_key(user)` | UserAPIKey with fake encrypted key |

---

## How to Write Chatbot Tests

### Pattern: Mixin + TestCase

```python
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from . import ChatbotTestMixin

BASE = "/api/v1/chatbot/"

class MyTests(ChatbotTestMixin, TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = self.create_user()
        self.session = self.create_session(self.user)

    def test_something(self):
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{BASE}chat-sessions/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
```

### Response Structures

**Paginated list responses:**
```python
resp.data["results"]  # The list of items
```

**Single object:**
```python
resp.data["title"]
resp.data["id"]
```

### Key Gotchas

- User passwords are always `"testpass123!"` (set in `_mixins.py`)
- Use `force_authenticate(user)` for API tests, not login flows
- `create_document()` does NOT create an actual file — it's metadata only
- `create_api_key()` creates a fake encrypted key — never use real keys in tests
- TokenUsage ViewSet is read-only — POST returns 405
- SystemPrompt uses `IsAdminOrReadOnly` — regular users can only read

---

## Test Coverage by ViewSet

| ViewSet | Tests | Scenarios |
|---------|-------|-----------|
| **ChatSession** | 15 | CRUD, archive/activate/pin actions, stats/analytics, admin sees all, soft-delete |
| **UserPreference** | 5 | me (auto-create), session-config, reset-defaults, update |
| **TokenUsage** | 5 | List, create-not-allowed (405), usage-stats, daily-usage, check-limits |
| **MessageFeedback** | 4 | Create, list scoped, admin review, stats |
| **UserDocument** | 8 | List, retrieve, process, process-already-done (409), retry, status, storage-stats, processing-stats |
| **SystemPrompt** | 9 | List public, create admin-only (403 for user), rate, duplicate, render, search, default |
| **UserTool** | 7 | List, create from registry, activate, deactivate, registry, seed, enabled |
| **UserAPIKey** | 7 | List, create (encrypted), retrieve (no raw key), set-default, deactivate, providers, usage-summary |
| **Schema** | 10 | swagger_fake_view for all 8 ViewSets + serializer dispatch |

---

## Model Test Coverage

| Model | Tests | Scenarios |
|-------|-------|-----------|
| **ChatSession** | 16 | Defaults, UUID PK, properties (thread_id, is_new, title_preview), state transitions (archive, activate, toggle_pin, soft_delete), analytics, class methods |
| **UserPreference** | 12 | Defaults, properties (has_usage_limits, is_dark_mode), get_session_config, reset_to_defaults, update_from_dict, get_or_create, OneToOne constraint |
| **TokenUsage** | 4 | Auto-calculate totals, str, calculate_cost, get_user_usage_today |
| **MessageFeedback** | 2 | Creation, is_positive/is_negative |
| **UserDocument** | 9 | Creation, file_size_mb/display, state transitions, retry, activate/deactivate, storage usage |
| **SystemPromptTemplate** | 10 | Creation, rating (valid/invalid), render, validate_variables, increment_usage, duplicate, get_default, slug unique |
| **UserTool** | 6 | Creation, activate/deactivate, increment_usage, effective_config, unique constraint, enable from registry |
| **UserAPIKey** | 7 | Creation, display_key mask, provider_name, has_limits, deactivate, increment_usage, get_default_key |

---

## Adding a New Test

1. Open the appropriate test file (or create a new one)
2. Add your test class following the existing patterns
3. Run with `--keepdb` for speed:

```bash
python manage.py test chatbot.tests.test_api_viewsets.MyNewClass --settings=config.settings.test -v 2 --keepdb
```

4. Update the test count in this file and in `backend/docs/current_status.md`

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
4. **No real files.** `create_document()` creates metadata records without actual file uploads. For file upload tests, use `SimpleUploadedFile` with small in-memory content.
5. **No real API keys.** `create_api_key()` uses a fake encrypted key. Never hard-code real keys.
