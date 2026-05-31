# Backend Guide — Django + Next.js AI Chatbot

> A practical reference for how the Django backend is structured, how to navigate it, and how to add things.

---

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Language | Python | 3.12 |
| Framework | Django | 5.2 |
| API | Django REST Framework | 3.17 |
| Auth | SimpleJWT (rest_framework_simplejwt) | 5.5 |
| API Docs | drf-spectacular + sidecar | 0.29 |
| Async | Channels (Daphne ASGI) | — |
| Task Queue | Celery + Redis | — |
| Vector DB | pgvector (PostgreSQL 17) | — |
| AI | LangChain + LangGraph | — |
| Caching | Redis | 7 |
| Admin Theme | Jazzmin | — |

---

## Project Structure

```
backend/
├── config/                  # Django project configuration
│   ├── settings/
│   │   ├── base.py          # Shared settings (apps, DRF, JWT, Celery, Channels)
│   │   ├── development.py   # Local dev (DB, Redis URLs, CORS, throttling)
│   │   ├── test.py          # Test overrides (MD5 hasher, dummy cache)
│   │   └── production.py    # Production settings
│   ├── urls.py              # Root URL config (v1 router + docs)
│   ├── asgi.py              # ASGI entry (Channels/WebSocket)
│   ├── wsgi.py              # WSGI entry
│   └── celery.py            # Celery app + autodiscover
│
├── apps/
│   ├── accounts/            # Users, auth, contacts
│   ├── chatbot/             # Core chatbot: sessions, documents, tools, vector storage
│   └── core/                # Shared: TimestampedModel, Country, permissions
│
├── docs/
│   ├── lessons/             # Tutorial series (10 Django + project lessons)
│   ├── backend_guide.md     # ← this file
│   ├── current_status.md    # What's done, what's next
│   └── vision.md            # Project direction and goals
│
├── static/                  # Collected static files
├── media/                   # User uploads (avatars, documents)
└── manage.py
```

---

## Apps

### `accounts` — Users & Authentication

**Models:** `CustomUser`, `UserContact`

Key points:
- `CustomUser` extends `AbstractUser` with `email` as `USERNAME_FIELD`
- Roles: `user` / `admin`
- `post_save` signal auto-creates a `UserContact` for every new user
- JWT auth with cookie support via `CustomJWTCookieAuthentication`

**API endpoints** (mounted at `/api/v1/accounts/`):

| Endpoint | ViewSet/View | Methods |
|----------|-------------|---------|
| `users/` | `CustomUserViewSet` | CRUD + actions below |
| `users/me/` | `@action detail=False` | GET current user |
| `users/{id}/verify-email/` | `@action detail=True` | POST verify |
| `users/{id}/change-password/` | `@action detail=True` | POST change |
| `users/{id}/profile-image/` | `@action detail=True` | GET avatar |
| `users/stats/` | `@action detail=False` | GET counts |
| `user-contacts/` | `UserContactViewSet` | CRUD |
| `auth/login/` | `CustomTokenObtainPairView` | POST |
| `auth/logout/` | `LogoutView` | POST |
| `auth/register/` | `RegisterView` | POST |
| `auth/password/reset/` | `PasswordResetView` | POST |
| `auth/email/verify/` | `EmailVerificationView` | GET/POST |
| `auth/csrf/` | `CSRFTokenView` | GET |

**Serializer pattern** — operation-based split:

```
CustomUserSerializer         → read (retrieve)
CustomUserListSerializer     → read (list)
CustomUserCreateSerializer   → POST create
CustomUserUpdateSerializer   → PATCH/PUT update
```

**Tests:** `accounts/tests/` — 57 tests across models, serializers, and API viewsets.

---

### `chatbot` — Core AI Chatbot

**Models (8):**

| Model | Purpose |
|-------|---------|
| `ChatSession` | Conversation thread (maps to LangGraph `thread_id`) |
| `UserPreference` | AI settings/preferences per user |
| `TokenUsage` | Token consumption and cost tracking |
| `MessageFeedback` | User ratings on AI responses |
| `UserDocument` | RAG file uploads with pgvector references |
| `SystemPromptTemplate` | Reusable system prompts |
| `UserTool` | Tool enable/disable + config (includes `TOOL_REGISTRY`) |
| `UserAPIKey` | Encrypted provider API keys |

**Services (9):**

| Service | File | Purpose |
|---------|------|---------|
| `VectorStorageService` | `vector_storage_service.py` | PGEngine + PGVectorStore for RAG |
| `DocumentProcessingService` | `document_processing_service.py` | File upload → text extraction → chunking → embedding |
| `MessageService` | `message_service.py` | LangGraph `PostgresSaver` checkpointing |
| `SummarizationService` | `summarization_service.py` | LangGraph node + pre-model hook |
| `ChatSessionService` | `chat_session_service.py` | Session CRUD |
| `TokenUsageService` | `token_usage_service.py` | Token counting and cost |
| `ToolService` | `tool_service.py` | Tool registry (stub) |
| `UserPreferenceService` | `user_preference_service.py` | Preference CRUD |
| `APIKeyService` | `api_key_service.py` | Encrypted key management |

**API:** `chatbot/api/urls.py` is empty — routes are commented out in `config/urls.py`. No chatbot API endpoints are wired yet.

---

### `core` — Shared

- `TimestampedModel` — abstract base with `created_at` / `updated_at`
- `Country` — geography model
- `permissions/` — access control classes

---

## Settings

| Setting | Value | Used by |
|---------|-------|---------|
| `PGVECTOR_CONNECTION_STRING` | `postgresql+psycopg://...` | VectorStorageService (SQLAlchemy) |
| `PG_CHECKPOINT_URI` | `postgresql://...` | MessageService (raw psycopg) |
| `DEFAULT_LLM_MODEL` | `gpt-4o-mini` | LangChain calls |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | VectorStorageService |
| `CELERY_BROKER_URL` | Redis DB 1 | Celery |
| `CHANNEL_LAYERS` | Redis DB 0 | Channels/WebSocket |

---

## Database Layout (Docker)

PostgreSQL 17 with pgvector creates 3 databases:

| Database | Purpose |
|----------|---------|
| `chatbot_db` | Django ORM (auth, sessions, documents, preferences) |
| `langchain_pgvector` | pgvector embeddings for RAG |
| `langchain_history` | LangGraph checkpoints (conversation state) |

Redis DBs: 0 = cache + Channels, 1 = Celery broker, 2 = Celery results.

---

## Adding a New API Endpoint

1. **Model** — define in `apps/<app>/models/`
2. **Serializer** — create operation-based serializers in `apps/<app>/api/serializers/`
3. **ViewSet** — create in `apps/<app>/api/views/` with `@extend_schema_view` + `@action`
4. **Router** — register in `apps/<app>/api/urls.py` with `DefaultRouter`
5. **Mount** — include in `config/urls.py`
6. **Test** — add to `apps/<app>/tests/test_api_viewsets.py`

```python
@extend_schema_view(
    list=extend_schema(tags=["Tag"], summary="List ..."),
    retrieve=extend_schema(tags=["Tag"], summary="Retrieve ..."),
)
@extend_schema(tags=["Tag"])
class MyModelViewSet(viewsets.ModelViewSet):
    queryset = MyModel.objects.select_related("...").all()
    serializer_class = MyModelSerializer

    def get_serializer_class(self):
        if self.action == "create":
            return MyModelCreateSerializer
        return MyModelSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return MyModel.objects.none()
        # ... scoped queryset

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        ...
```

---

## Running Tests

```bash
cd backend
source venv/bin/activate

# All accounts tests
python manage.py test accounts.tests --settings=config.settings.test -v 2

# Specific module
python manage.py test accounts.tests.test_api_viewsets --settings=config.settings.test -v 2

# With --keepdb for speed
python manage.py test accounts.tests --settings=config.settings.test -v 2 --keepdb
```

---

## Key Commands

```bash
python manage.py runserver                     # Dev server (Daphne/ASGI)
python manage.py spectacular --validate        # Validate OpenAPI schema
python manage.py spectacular --file schema.yml # Export schema
celery -A config worker --loglevel=info         # Celery worker
celery -A config beat --loglevel=info           # Celery beat scheduler
python manage.py test accounts.tests --settings=config.settings.test  # Tests
```
