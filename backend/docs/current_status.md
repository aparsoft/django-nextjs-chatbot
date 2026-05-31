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
| Tests | ✅ | 57 tests (models + serializers + API viewsets) |
| Signal | ✅ | Auto-creates `UserContact` on user creation |
| Spectacular extension | ✅ | `CustomJWTCookieAuthenticationScheme` registered |

---

## `chatbot` App — ⚠️ Services Built, API Not Wired

| Layer | Status | Details |
|-------|--------|---------|
| Models (8) | ✅ | ChatSession, UserPreference, TokenUsage, MessageFeedback, UserDocument, SystemPromptTemplate, UserTool, UserAPIKey |
| Services (9) | ✅ | All service classes implemented (see backend_guide.md) |
| Vector storage | ✅ | `PGEngine` + `PGVectorStore` with singleton engine, 1536-dim embeddings |
| Document processing | ✅ | File upload → text extraction → chunking → embedding pipeline |
| Message service | ✅ | LangGraph `PostgresSaver` checkpointing |
| Summarization service | ✅ | LangGraph node + `pre_model_hook` for `create_react_agent` |
| API endpoints | ❌ Not wired | `chatbot/api/urls.py` is empty, routes commented out in `config/urls.py` |
| Serializers | ⚠️ Partial | `chat_session_serializers.py` exists, others missing |
| ViewSets | ❌ | `chatbot/api/views/` is empty |
| Tests | ❌ | `chatbot/tests.py` is empty |
| Management commands | ❌ | No commands written |
| Celery tasks | ❌ | No `tasks.py` files exist anywhere |

---

## `core` App — ⚠️ Partial

| Layer | Status | Details |
|-------|--------|---------|
| `TimestampedModel` | ✅ | Abstract base with `created_at` / `updated_at` |
| `Country` | ✅ | Geography model |
| Permissions | ⚠️ | `__init__.py` exports many classes but source `.py` files are missing (only `.pyc`) |
| API | ❌ | `urls.py` and `views/` are empty |

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

- `/api/v1/schema/` — JSON/YAML schema (17 endpoints, 0 errors)
- `/api/v1/docs/` — Swagger UI with JWT auth support
- `/api/v1/redoc/` — ReDoc documentation
- Tags: Authentication (8), Users (9), User Contacts (5), Profile (1)

---

## Priority Checklist (What to Build Next)

1. **Chatbot API** — Wire `chatbot/api/urls.py`, create serializers + ViewSets for ChatSession, UserDocument, etc.
2. **LangGraph agent graph** — Build the actual `create_react_agent` graph using the services (VectorStorage, MessageService, SummarizationService, ToolService)
3. **Celery tasks** — `process_document_task`, `send_email_task`, etc.
4. **Frontend** — Chat UI, auth pages, document upload
5. **WebSocket consumers** — Real-time streaming for chat responses
6. **Core permissions** — Restore source `.py` files for the permission classes

---

## Test Coverage Summary

| App | Tests | Status |
|-----|------:|--------|
| `accounts` | 57 | ✅ All passing |
| `chatbot` | 0 | ❌ No tests |
| `core` | 0 | ❌ No tests |
| **Total** | **57** | |
