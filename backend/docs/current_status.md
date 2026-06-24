# Current Status — Django + Next.js AI Chatbot

> Snapshot of what's built, what's wired, and what's still a stub. Updated June 2026.

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
| Google OAuth | ✅ | `GoogleLoginView` — ID-token verification via `google-auth`, mints our JWTs |
| Cookie helper | ✅ | `accounts/services/cookies.py` — `set_auth_cookies` / `clear_auth_cookies` (single source of truth) |
| Cookie max-age bug | ✅ Fixed | Login/refresh/logout views now use the centralized helper (was hardcoded 7d/1h) |
| Serializers | ✅ | Operation-based split: Read / List / Create / Update |
| ViewSets | ✅ | Action-based with `@action url_path` for custom routes |
| Permissions | ✅ | Admin sees all, regular user sees self |
| API Docs | ✅ | `@extend_schema` on every view, 0 errors/0 warnings |
| Tests | ✅ | 114 tests (models + serializers + API viewsets + auth views + Google OAuth) |
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
| Agent service | ✅ | `create_agent` (langchain v1) + `SummarizationMiddleware` + tool loading + `ChatAgentOrchestrator` |
| WebSocket consumer | ✅ | `ChatConsumer` for real-time chat via `ws/chat/<session_id>/` |
| Management command | ✅ | `run_chat` — interactive CLI chatbot for testing and intern onboarding |
| Model tests | ✅ | 66 tests across 8 test classes with shared `ChatbotTestMixin` |
| Agent tests | ✅ | 49 tests: orchestrator, middleware, tools, checkpointer, management command |
| API/serializer/service tests | ❌ | No viewset, serializer, or service-level tests |
| Admin registration | ❌ | `admin/__init__.py` is empty — none of the 8 models registered |
| Celery tasks | ❌ | No `tasks.py` files exist — TODOs in `UserDocumentViewSet.process()` and `retry()` |
| Tool loading | ⚠️ | Calculator + document_retriever implemented; web_search & code_executor still stubs |

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

## Frontend — ✅ Auth Wired, Chat Stub

| Component | Status |
|-----------|--------|
| Next.js 16 + React 19 | ✅ Installed |
| Tailwind CSS v4 | ✅ Installed |
| TanStack Query | ✅ `@tanstack/react-query` — auth hooks (`useLogin`, `useLogout`, `useCurrentUser`, `useRegister`, `useGoogleLogin`) |
| BFF proxy pattern | ✅ Route handlers: login, refresh, logout, register, me, ws-token, social/google, catch-all proxy |
| `proxy.js` | ✅ Next.js 16 `proxy.js` (replaces deprecated `middleware.js`) — cookie-existence route protection |
| Auth pages | ✅ `app/auth/login/`, `app/auth/register/`, `app/auth/LogoutButton` |
| Lib modules | ✅ `django.js`, `cookies.js`, `jwt.js`, `refresh.js`, `server-auth.js`, `api.js`, `api-client.js`, `auth-hooks.js` |
| Tests | ✅ 41 tests (jwt, refresh lock, cookies, django, auth-hooks) |
| Chat UI | ❌ Not started |
| Dashboard | ❌ Not started |

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
| `accounts` | 114 | ✅ All passing (models + serializers + API viewsets + auth views + Google OAuth) |
| `chatbot` | 115 | ✅ Model (66) + Agent service (49) tests passing; ❌ No API/serializer tests |
| `core` | 0 | ❌ No tests |
| **Total** | **229** | |

---

## Open TODOs in Codebase

| Location | Description |
|----------|-------------|
| `chatbot/api/views/user_document_views.py` | `process()` and `retry()` need Celery task integration |
| `chatbot/services/chat_session_service.py` | `hard_delete_session()` needs LangGraph checkpoint cleanup |
| `chatbot/services/agent_service.py` | `web_search` and `code_executor` tools are stubs — need Tavily/sandbox integration |

---

## Priority Checklist (What to Build Next)

1. **Chatbot API tests** — ViewSet tests, serializer tests, service-level tests
2. **Remaining tools** — Implement `web_search` (Tavily) and `code_executor` tools
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
| `docs/AUTHENTICATION.md` | Gold-standard backend auth guide (JWT + Google OAuth + cookie helper + threat model + runbook) |
| `docs/lessons/` | 10-lesson Django tutorial series |
