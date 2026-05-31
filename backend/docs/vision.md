# Vision — ConvoInsight AI Chatbot

> What we're building and why. The north star for every design decision.

---

## The Mission

Build a **conversational AI chatbot platform** that teaches developers how to integrate AI into full-stack web applications. Every piece of code should be clear enough for an intern to understand, robust enough for a tutorial series, and structured enough to grow into a real product.

**We are building in public** — this is the [Aparsoft YouTube tutorial series](https://youtube.com/@aparsoft). The codebase IS the curriculum.

---

## Product Vision

ConvoInsight is a **Customer Conversational Intelligence Platform** — a chatbot that:

1. **Converses** with users via a clean chat interface
2. **Remembers** conversation context across sessions (LangGraph checkpoints)
3. **Knows things** through uploaded documents (RAG with pgvector)
4. **Uses tools** — web search, calculators, custom integrations
5. **Manages costs** — token usage tracking, API key management per user

---

## Architecture Principles

### Service Layer, Not Fat Views

Business logic lives in `services/`, not in views or serializers. Views are thin HTTP adapters that call services. This keeps things testable and reusable.

```
Request → ViewSet → Service → Model/External API
                ↘ Serializer (data shaping only)
```

### Operation-Based Serializers

One serializer per operation (`Read`, `Create`, `Update`), not one monolith. Makes validation explicit and OpenAPI schemas accurate.

### Action-Based ViewSets

Custom routes use `@action(url_path=...)` so the `DefaultRouter` auto-discovers everything. No manual URL wiring.

```
GET  /users/me/                → @action(detail=False)
POST /users/{id}/verify-email/ → @action(detail=True, url_path="verify-email")
```

### PGVector for RAG, LangGraph for State

- **pgvector** stores document embeddings — semantic search over user uploads
- **LangGraph** manages conversation state via `PostgresSaver` checkpointer
- **`PGEngine`** singleton manages the SQLAlchemy connection pool

These are separate concerns: vector storage is NOT the same as conversation state.

### Everything Documented

Every endpoint has `@extend_schema` decorators. Swagger UI at `/api/v1/docs/` is the source of truth for the API. Zero warnings in `spectacular --validate`.

---

## Technology Decisions

| Choice | Why |
|--------|-----|
| **Django + DRF** | Mature, batteries-included, great for teaching. DRF ViewSets + routers = clean API with minimal boilerplate. |
| **PostgreSQL + pgvector** | One database for everything — relational data AND vector embeddings. No separate vector DB to manage. |
| **LangGraph** | Graph-based agent framework. Checkpointing, tool calling, and state management built in. Better than raw LangChain for multi-turn conversations. |
| **Celery + Redis** | Async task processing (document upload, email sending). Redis doubles as cache and Channels layer. |
| **Next.js** | Modern React with SSR. Clean separation from the Django backend. |
| **drf-spectacular** | Best OpenAPI schema generator for DRF. Auto-documented endpoints with `@extend_schema`. |

---

## Target Architecture (End State)

```
┌─────────────┐     ┌──────────────────────────────────────────┐
│   Next.js   │────▶│            Django Backend                │
│   Frontend  │     │                                          │
│             │◀────│  ┌────────────┐   ┌───────────────────┐ │
└─────────────┘     │  │ DRF API    │   │ LangGraph Agent   │ │
                    │  │ ViewSets   │──▶│ (create_react_    │ │
                    │  │            │   │  agent)            │ │
                    │  └────────────┘   └───────┬───────────┘ │
                    │                          │              │
                    │  ┌────────────┐   ┌──────▼───────────┐ │
                    │  │ Services   │   │ Tools             │ │
                    │  │ (9 files)  │   │ - RAG search      │ │
                    │  │            │   │ - Web search       │ │
                    │  └────────────┘   │ - Summarization   │ │
                    │                   └───────────────────┘ │
                    │                                          │
                    │  ┌────────────────────────────────────┐  │
                    │  │ Data Layer                          │  │
                    │  │ ┌──────────┐ ┌────────┐ ┌────────┐ │  │
                    │  │ │ Django   │ │ pgvector│ │ LangGr │ │  │
                    │  │ │ ORM      │ │ embeds  │ │aph chk │ │  │
                    │  │ │ (auth,   │ │ (RAG)   │ │points  │ │  │
                    │  │ │  prefs)  │ │         │ │        │ │  │
                    │  │ └──────────┘ └────────┘ └────────┘ │  │
                    │  └────────────────────────────────────┘  │
                    └──────────────────────────────────────────┘
```

---

## What "Done" Looks Like

- [ ] Chat API: create session, send message, stream response, get history
- [ ] Document upload API: upload → process → index → search via RAG
- [ ] LangGraph agent graph with tools (RAG search, web search, summarization)
- [ ] Token usage tracking and cost reporting
- [ ] WebSocket streaming for real-time chat responses
- [ ] Frontend: chat UI, auth flow, document management
- [ ] Celery tasks for async document processing and email
- [ ] Full test coverage across all apps (target: 200+ tests)
- [ ] Production deployment guide (Docker, Nginx, SSL)

---

## What This Is NOT

- Not an enterprise SaaS platform (yet)
- Not a multi-tenant system
- Not trying to replace ChatGPT
- Not over-engineered — every pattern exists because it teaches something

---

## Audience

1. **Interns** joining Aparsoft — they should be productive in a week
2. **YouTube viewers** — they follow along at home, so code must be readable
3. **Future us** — six months from now we need to remember why we made each choice

If a design decision doesn't serve one of these audiences, reconsider it.
