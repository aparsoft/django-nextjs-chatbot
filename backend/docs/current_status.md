# Current Status — Django + Next.js AI Chatbot

> Snapshot of what's built, what's wired, and what's still a stub. Updated May 2026.

---

## Infrastructure ✅

| Component | Status | Details |
|-----------|--------|---------|
| PostgreSQL 17 + pgvector | ✅ Running | 3 DBs via `docker/init-db.sh` |
| Redis 7 | ✅ Running | 3 DBs (cache, broker, results) |
| Docker Compose | ✅ Complete | Only infra services — Django/Celery run locally |
| Celery config | ✅ Wired | `autodiscover_tasks()` ready, no tasks written yet |
| Channels/WebSocket | ⚠️ Partial | ASGI + channels_redis configured, no consumers, routing commented out |

---

## `accounts` App — ✅ Complete

| Layer | Status | Details |
|-------|--------|---------|
| Models | ✅ | `CustomUser` (user/admin roles), `UserContact` |
| Auth (JWT) | ✅ | Login, logout, register, password reset, email verification, CSRF |
| Serializers | ✅ | Operation-based split: Read / List / Create / Update |
| ViewSets | ✅ | Action-based with `@action url_path` for custom routes |
| Permissions | ✅ | Admin sees all, regular user sees self |
| API Docs | ✅ | `@extend_schema` on every view, 0 errors/0 warnings |
| Tests | ✅ | 99 tests (models + serializers + API viewsets + auth views) |
| Signal | ✅ | Auto-creates `UserContact` on user creation |
| Spectacular extension | ✅ | `CustomJWTCookieAuthenticationScheme` registered |

---

## `chatbot` App — ✅ API Wired, Tests Partial

| Layer | Status | Details |
|-------|--------|---------|
| Models (8) | ✅ | ChatSession, UserPreference, TokenUsage, MessageFeedback, UserDocument, SystemPromptTemplate, UserTool, UserAPIKey |
| Serializers (31) | ✅ | All 8 model serializer groups implemented (Read / List / Create / Update split) |
| ViewSets (8) | ✅ | All 8 ViewSets with custom actions, filtering, ordering, search, OpenAPI docs |
| URL routing | ✅ | `DefaultRouter` with all 8 ViewSets, mounted at `/api/v1/chatbot/` |
| Services (9) | ✅ | All service classes implemented (see backend_guide.md) |
| Vector storage | ✅ | `PGEngine` + `PGVectorStore` with singleton engine, 1536-dim embeddings |
| Document processing | ✅ | File upload → text extraction → chunking → embedding pipeline |
| Message service | ✅ | LangGraph `PostgresSaver` checkpointing |
| Summarization service | ✅ | LangGraph node + `pre_model_hook` for `create_react_agent` |
| Model tests | ✅ | 66 tests across 8 test classes with shared `ChatbotTestMixin` |
| API/serializer/service tests | ❌ | No viewset, serializer, or service-level tests |
| Admin registration | ❌ | `admin/__init__.py` is empty — none of the 8 models registered |
| Management commands | ❌ | No commands written (needed for tool seeding) |
| Celery tasks | ❌ | No `tasks.py` files exist — TODOs in `UserDocumentViewSet.process()` and `retry()` |
| Tool loading | ⚠️ | `ToolService.get_tool_instances()` returns `[]` — LangChain tool loading not implemented |

### Chatbot API Endpoints

All mounted at `/api/v1/chatbot/`:

| Endpoint | ViewSet | Methods | Custom Actions |
|----------|---------|---------|----------------|
| `chat-sessions/` | `ChatSessionViewSet` | CRUD | `archived`, `pinned`, `stats`, `archive`, `activate`, `pin`, `analytics` |
| `preferences/` | `UserPreferenceViewSet` | CRUD | `me`, `session_config`, `reset_defaults` |
| `token-usage/` | `TokenUsageViewSet` | Read-only | `usage_stats`, `daily_usage`, `check_limits`, `model_breakdown` |
| `message-feedback/` | `MessageFeedbackViewSet` | CRUD | `review` (admin), `stats` |
| `documents/` | `UserDocumentViewSet` | CRUD | `process`, `retry`, `status`, `storage_stats`, `processing_stats` |
| `system-prompts/` | `SystemPromptViewSet` | CRUD | `rate`, `duplicate`, `render`, `by_category`, `search`, `default` |
| `tools/` | `UserToolViewSet` | CRUD | `activate`, `deactivate`, `rate_limit_status`, `registry`, `seed`, `enabled` |
| `api-keys/` | `UserAPIKeyViewSet` | CRUD | `validate`, `set_default`, `deactivate`, `providers`, `usage_summary` |

---

## `core` App — ✅ Complete

| Layer | Status | Details |
|-------|--------|---------|
| `TimestampedModel` | ✅ | Abstract base with `created_at` / `updated_at` |
| `Country` | ✅ | Geography model |
| Permissions | ✅ | 4 classes in `base.py`: `IsOwnerOrAdmin`, `IsOwner`, `IsAdminOrReadOnly`, `IsAdminUser` |
| API | ❌ | `urls.py` and `views/` are empty (shared utility app, no own endpoints) |

---

## Frontend — ❌ Stub

| Component | Status |
|-----------|--------|
| Next.js 15 + React 19 | ✅ Installed |
| Tailwind CSS v4 | ✅ Installed |
| Pages | ❌ Only root `page.js` — no chat, auth, or dashboard pages |
| Components | ❌ No `components/`, `lib/`, or `hooks/` directories |
| API layer | ❌ No axios/fetch integration |

---

## OpenAPI Docs — ✅

- `/api/v1/schema/` — JSON/YAML schema
- `/api/v1/docs/` — Swagger UI with JWT auth support
- `/api/v1/redoc/` — ReDoc documentation
- Tags: Authentication (11), Users (9), User Contacts (5), Profile (1), plus 8 chatbot tags

---

## Test Coverage Summary

| App | Tests | Status |
|-----|------:|--------|
| `accounts` | 99 | ✅ All passing (models + serializers + API viewsets + auth views) |
| `chatbot` | 66 | ✅ Model tests passing; ❌ No API/serializer/service tests |
| `core` | 0 | ❌ No tests |
| **Total** | **165** | |

---

## Open TODOs in Codebase

| Location | Description |
|----------|-------------|
| `chatbot/services/tool_service.py` | `get_tool_instances()` returns `[]` — needs LangChain tool loading |
| `chatbot/api/views/user_document_views.py` | `process()` and `retry()` need Celery task integration |
| `chatbot/services/chat_session_service.py` | `hard_delete_session()` needs LangGraph checkpoint cleanup |

---

## Priority Checklist (What to Build Next)

1. **Chatbot API tests** — ViewSet tests, serializer tests, service-level tests
2. **LangGraph agent graph** — Build the actual `create_react_agent` graph using the services (VectorStorage, MessageService, SummarizationService, ToolService)
3. **Celery tasks** — `process_document_task`, `cleanup_old_sessions_task`, etc.
4. **Admin registration** — Register all 8 chatbot models in Django admin
5. **Management commands** — `seed_tools` to populate `TOOL_REGISTRY` defaults
6. **Frontend** — Chat UI, auth pages, document upload
7. **WebSocket consumers** — Real-time streaming for chat responses

---

## Documentation

| File | Description |
|------|-------------|
| `docs/backend_guide.md` | Project structure, patterns, and how-to guide |
| `docs/current_status.md` | This file — what's done, what's next |
| `docs/vision.md` | Project direction and goals |
| `docs/AUTHENTICATION.md` | Detailed auth flow documentation |
| `docs/lessons/` | 10-lesson Django tutorial series |
