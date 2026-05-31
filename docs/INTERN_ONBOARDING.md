# 🚀 Aparsoft Interns — Project Onboarding Guide

> **Welcome to Aparsoft!** This guide will take you from zero to contributing code on the AI Chatbot project. Take it step by step — don't rush, ask questions, and have fun!

---

## 📋 Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Project Overview](#2-project-overview)
3. [Day 1: Setup](#3-day-1-setup)
4. [Day 2: Understand the Architecture](#4-day-2-understand-the-architecture)
5. [Day 3: Django Basics](#5-day-3-django-basics)
6. [Day 4: Models & ORM](#6-day-4-models--orm)
7. [Day 5: APIs, Serializers, ViewSets](#7-day-5-apis-serializers-viewsets)
8. [Day 6: LangGraph & LangChain](#8-day-6-langgraph--langchain)
9. [Day 7: Management Commands](#9-day-7-management-commands)
10. [Your First Task](#10-your-first-task)
11. [Troubleshooting](#11-troubleshooting)
12. [Resources](#12-resources)

---

## 1. Prerequisites

Before you start, make sure you have these installed:

| Tool | Version | Why | Install |
|------|---------|-----|---------|
| **Docker Desktop** | Latest | Runs PostgreSQL + Redis for you | [docker.com](https://www.docker.com/products/docker-desktop/) |
| **Git** | Latest | Version control | [git-scm.com](https://git-scm.com/) |
| **VS Code** | Latest | Code editor (recommended) | [code.visualstudio.com](https://code.visualstudio.com/) |
| **Python** | 3.12+ | Backend language | [python.org](https://www.python.org/downloads/) |
| **Node.js** | 20+ | Frontend runtime | [nodejs.org](https://nodejs.org/) |

**VS Code Extensions you should install:**
- Python (Microsoft)
- Django (Baptiste Darthenay)
- Docker (Microsoft)
- GitLens (GitKraken)
- Prettier (Prettier)
- ESLint (Microsoft)

---

## 2. Project Overview

### What are we building?

An **AI Chatbot** web application where users can:
- Chat with an AI assistant (like ChatGPT)
- Upload documents and ask questions about them (RAG — Retrieval Augmented Generation)
- Give feedback on AI responses (thumbs up/down)
- Customize their AI settings (model, temperature, etc.)

### Tech Stack

```
┌──────────────────────────────────────────────────────┐
│                    Frontend                           │
│              Next.js 15 + React 19                    │
│              (TypeScript, Tailwind CSS)               │
└──────────────────────┬───────────────────────────────┘
                       │ REST API + WebSocket
┌──────────────────────▼───────────────────────────────┐
│                    Backend                            │
│              Django 5.2 + DRF                         │
│              LangGraph + LangChain                    │
│              Celery (background tasks)                │
└───┬──────────────┬──────────────┬────────────────────┘
    │              │              │
    ▼              ▼              ▼
┌────────┐  ┌──────────┐  ┌──────────────┐
│Postgres│  │  Redis   │  │  OpenAI API  │
│pgvector│  │  (cache, │  │  (GPT models)│
│        │  │  broker) │  │              │
└────────┘  └──────────┘  └──────────────┘
```

### Where does everything live?

```
django-nextjs-chatbot/
├── backend/               ← Django project (YOUR MAIN FOCUS)
│   ├── apps/
│   │   ├── accounts/      ← User authentication
│   │   ├── chatbot/       ← AI chatbot features ⭐
│   │   └── core/          ← Shared utilities
│   ├── config/            ← Django settings
│   └── manage.py          ← Django command-line tool
├── frontend/              ← Next.js app
├── docker/                ← Docker init scripts
├── docs/                  ← Documentation (this file!)
└── docker-compose.yml     ← Docker services config
```

---

## 3. Day 1: Setup

### Step 1: Clone the repo

```bash
git clone <repo-url>
cd django-nextjs-chatbot
```

### Step 2: Set up environment variables

```bash
# Copy the template
cp .env.example .env

# Open it and fill in your OpenAI API key (ask your mentor for one)
# The rest works with defaults for local development
```

### Step 3: Start the Docker infrastructure

This starts PostgreSQL (with pgvector) and Redis. **You only need these two — you'll run Django locally for hot-reload.**

```bash
# Start only the databases
docker compose up db redis -d

# Wait ~10 seconds, then check they're healthy:
docker compose ps
```

You should see:
```
NAME             STATUS
chatbot-db       Up (healthy)
chatbot-redis    Up (healthy)
```

**What's running:**
| Service | Host Port | What it does |
|---------|-----------|-------------|
| PostgreSQL + pgvector | `localhost:5433` | Three databases: `chatbot_db`, `langchain_pgvector`, `langchain_history` |
| Redis | `localhost:6380` | Cache, Celery broker, WebSocket channels |

> 💡 **Why non-standard ports?** So Docker doesn't clash with any Postgres/Redis you might already have on your machine.

### Step 4: Create a Python virtual environment

```bash
cd backend

# Create venv
python3 -m venv venv

# Activate it
# On Linux/Mac:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 5: Run migrations & create superuser

```bash
# Create database tables
python manage.py migrate

# Create your admin user
python manage.py createsuperuser
# Follow the prompts (email, password)

# Start the dev server
python manage.py runserver
```

### Step 6: Verify everything works

Open these URLs:
- 🏠 Django Admin: http://localhost:8000/chatbot-admin/
- 📊 API Root: http://localhost:8000/api/v1/
- ✅ If you see the admin login page, you're golden!

---

## 4. Day 2: Understand the Architecture

### The Request-Response Cycle (Django)

This is THE most important concept. Memorize this flow:

```
User clicks "Send Message"
        │
        ▼
┌──────────────────┐
│   urls.py         │  ← URL routing: /api/v1/chat/ → ChatSessionViewSet
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│   ViewSet         │  ← Business logic orchestration
│   (thin!)         │     Calls model methods, returns Response
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│   Serializer      │  ← Data validation + JSON conversion
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│   Model           │  ← Database layer (FATTY models!)
│   (fat!)          │     Business logic lives here
└──────────────────┘
```

### Our Philosophy: Fatty Models, Thin Viewsets

```
❌ BAD — Logic in the viewset:
    def create(self, request):
        prefs = UserPreference.objects.get(user=request.user)
        session = ChatSession.objects.create(
            user=request.user,
            model_name=prefs.default_model,
            temperature=prefs.default_temperature,
        )

✅ GOOD — Logic in the model, viewset is thin:
    def create(self, request):
        session = ChatSession.create_for_user(request.user)
```

**Rule of thumb:** If it's business logic, put it in the model. The viewset should be ~5-10 lines max.

### What Django stores vs What LangGraph stores

This is the second most important concept:

```
┌─────────────────────────────────┐  ┌──────────────────────────────┐
│     Django Models (ORM)         │  │   LangGraph Checkpointer     │
│     PostgreSQL: chatbot_db      │  │   PostgreSQL: langchain_history│
├─────────────────────────────────┤  ├──────────────────────────────┤
│ ✓ Session titles & metadata     │  │ ✓ Actual chat messages        │
│ ✓ User preferences             │  │ ✓ Conversation state          │
│ ✓ Token usage & costs          │  │ ✓ Checkpoints (snapshots)     │
│ ✓ Message feedback             │  │ ✓ Automatic summaries         │
│ ✓ File upload metadata         │  │                              │
│ ✓ Tool configurations          │  │                              │
│ ✗ NOT messages!                │  │ ✗ NOT user preferences!      │
└─────────────────────────────────┘  └──────────────────────────────┘
         ▲                                      ▲
         │                                      │
    Django ORM queries                    LangGraph API calls
    ChatSession.objects.filter()          checkpointer.get_state()
```

**Why?** LangGraph's checkpointer is purpose-built for conversation state. We don't duplicate that in Django models — we just store metadata (titles, settings, analytics).

---

## 5. Day 5: Django Basics

### Key Concepts

1. **MVT Pattern** — Model, View, Template (we use ViewSets instead of Templates)
2. **Apps** — Self-contained modules. Our main app is `chatbot/`
3. **Migrations** — How Django creates database tables from Python code
4. **ORM** — Object-Relational Mapper. Write Python, get SQL.

### Essential Commands

```bash
# Database
python manage.py makemigrations          # Generate migration files from model changes
python manage.py migrate                 # Apply migrations to database
python manage.py showmigrations          # See which migrations have been applied

# Server
python manage.py runserver               # Start dev server (localhost:8000)
python manage.py runserver 0.0.0.0:8000  # Start on all interfaces

# Shell — interactive Python with Django loaded
python manage.py shell
>>> from apps.chatbot.models import ChatSession
>>> ChatSession.objects.count()
>>> session = ChatSession.create_for_user(user)
>>> session.get_langgraph_config()

# Superuser
python manage.py createsuperuser         # Create admin user

# Static files
python manage.py collectstatic           # Gather static files
```

### The Settings Architecture

```
config/settings/
├── base.py          ← Shared settings (all environments)
├── development.py   ← Local dev (DEBUG=True, local DB)
└── production.py    ← Production (DEBUG=False, managed DB)
```

> ⚠️ **Never put secrets in settings files!** Use environment variables via `python-decouple`.

---

## 6. Day 4: Models & ORM

### Our 8 Models

Read each model file in `backend/apps/chatbot/models/`:

| Model | File | Teaches You |
|-------|------|------------|
| `ChatSession` | `chat_session.py` | UUID primary keys, FK, JSON fields |
| `UserPreference` | `user_preference.py` | OneToOneField, defaults pattern |
| `TokenUsage` | `user_preference.py` | DecimalField, aggregates, @classmethod |
| `MessageFeedback` | `message_feedback.py` | unique_together, admin review pattern |
| `UserDocument` | `user_document.py` | FileField, state machines, pgvector |
| `SystemPromptTemplate` | `system_prompt.py` | SlugField, template rendering |
| `UserTool` | `user_tool.py` | TOOL_REGISTRY pattern, config merging |
| `UserAPIKey` | `user_api_key.py` | BinaryField, Fernet encryption |

### Model Method Patterns to Learn

Every model in our project follows these patterns:

```python
class MyModel(TimestampedModel):
    # ... fields ...

    # 1. Properties — computed values (no DB query)
    @property
    def display_name(self):
        return f"{self.first_name} {self.last_name}"

    # 2. Instance methods — actions on a single row
    def archive(self):
        self.is_active = False
        self.save(update_fields=["is_active"])

    # 3. Class methods — queries / factories
    @classmethod
    def get_active_for_user(cls, user):
        return cls.objects.filter(user=user, is_active=True)

    @classmethod
    def create_for_user(cls, user, **kwargs):
        return cls.objects.create(user=user, **kwargs)

    # 4. to_display_dict — for API responses
    def to_display_dict(self):
        return {"id": self.id, "name": self.display_name}
```

### Practice Exercises

```bash
python manage.py shell

# 1. Create a user preference
>>> from django.contrib.auth import get_user_model
>>> User = get_user_model()
>>> user = User.objects.first()

# 2. Create preferences
>>> from apps.chatbot.models import UserPreference
>>> prefs = UserPreference.get_or_create_for_user(user)
>>> prefs.default_model
'gpt-5-mini'

# 3. Create a session using preferences
>>> from apps.chatbot.models import ChatSession
>>> session = ChatSession.create_for_user(user, title="My First Chat")
>>> session.thread_id  # This is the LangGraph thread ID!
'550e8400-e29b-41d4-a716-446655440000'

# 4. Get the LangGraph config
>>> session.get_langgraph_config()
{'configurable': {'thread_id': '550e8400-...'}}

# 5. Query active sessions
>>> ChatSession.get_active_for_user(user)
<QuerySet [<ChatSession: My First Chat (admin@aparsoft.com)>]>

# 6. Seed tools for user
>>> from apps.chatbot.models import UserTool
>>> UserTool.seed_all_tools(user)
>>> UserTool.get_enabled_for_user(user)
[]
# (All seeded as disabled — user opts in)

# 7. Enable a tool
>>> tool = UserTool.enable_tool(user, "web_search")
>>> tool.get_effective_config()  # Merged config
{'max_results': 5}
```

---

## 7. Day 5: APIs, Serializers, ViewSets

### How our APIs work

We use **Django REST Framework (DRF)** with ViewSets:

```
HTTP Request → URL Router → ViewSet → Serializer → Model → Response
```

### The Thin ViewSet Pattern

```python
# chatbot/api/views/chat_session_views.py

class ChatSessionViewSet(viewsets.ModelViewSet):
    serializer_class = ChatSessionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ChatSession.get_active_for_user(self.request.user)

    def perform_create(self, serializer):
        session = ChatSession.create_for_user(
            self.request.user,
            **serializer.validated_data
        )
        serializer.instance = session
```

**That's it.** The viewset doesn't know about preferences or defaults — the model handles all of that.

### URL Routing

```python
# chatbot/api/urls.py

from rest_framework.routers import DefaultRouter
from .views import ChatSessionViewSet

router = DefaultRouter()
router.register(r'sessions', ChatSessionViewSet, basename='chat-session')

urlpatterns = router.urls
```

This auto-generates:
- `GET /api/v1/sessions/` → List sessions
- `POST /api/v1/sessions/` → Create session
- `GET /api/v1/sessions/{id}/` → Get session
- `PATCH /api/v1/sessions/{id}/` → Update session
- `DELETE /api/v1/sessions/{id}/` → Delete session

---

## 8. Day 6: LangGraph & LangChain

### What is LangGraph?

LangGraph is a framework for building **stateful AI agents**. It handles:
- Conversation history (checkpoints)
- Tool usage (web search, code execution)
- Summarization (when conversations get long)
- Error recovery (replay from checkpoints)

### How it connects to our Django models

```python
from apps.chatbot.models import ChatSession

# 1. Django creates the session (metadata)
session = ChatSession.create_for_user(user)

# 2. LangGraph uses the session ID as thread_id
config = session.get_langgraph_config()
# → {"configurable": {"thread_id": "uuid-here"}}

# 3. LangGraph stores messages in its own checkpointer
#    (PostgreSQL: langchain_history database)
response = agent.invoke({"messages": [HumanMessage(content="Hello")]}, config)

# 4. Django updates analytics
session.update_analytics(message_count=2, tokens_used=150)

# 5. TokenUsage tracks the cost
TokenUsage.create_from_response(user, session, response)
```

### What is pgvector?

pgvector is a PostgreSQL extension that stores **vector embeddings** — mathematical representations of text. When a user uploads a document:

1. Document text is split into chunks
2. Each chunk is converted to a vector (array of numbers) by OpenAI
3. Vectors are stored in PostgreSQL with pgvector
4. When the user asks a question, their question is also vectorized
5. pgvector finds the most similar chunks (semantic search)
6. Those chunks are sent to the AI as context

```
User uploads "Python Guide.pdf"
        │
        ▼
   Text Splitter → 50 chunks
        │
        ▼
   OpenAI Embeddings → 50 vectors (each is 1536 numbers)
        │
        ▼
   pgvector stores them in: langchain_pgvector database
        │
        ▼
   User asks "How do I create a class?"
        │
        ▼
   pgvector finds the 5 most similar chunks
        │
        ▼
   AI gets those chunks + the question → great answer!
```

---

## 9. Day 7: Management Commands

Management commands are CLI scripts that run Django operations. They live in:

```
apps/chatbot/management/commands/
├── seed_demo.py           # Create demo data
├── seed_tools.py          # Seed TOOL_REGISTRY for all users
└── cleanup_sessions.py    # Archive old sessions
```

### Anatomy of a Management Command

```python
# management/commands/seed_tools.py

from django.core.management.base import BaseCommand
from apps.chatbot.models import UserTool
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Seed tools from TOOL_REGISTRY for all users'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            help='Seed for a specific user only',
        )

    def handle(self, *args, **options):
        if options['user_id']:
            users = User.objects.filter(id=options['user_id'])
        else:
            users = User.objects.all()

        for user in users:
            results = UserTool.seed_all_tools(user)
            created = sum(1 for _, c in results if c)
            self.stdout.write(
                self.style.SUCCESS(f"Seeded {created} tools for {user.email}")
            )

        self.stdout.write(self.style.SUCCESS("Done!"))
```

### Running Commands

```bash
python manage.py seed_tools                # All users
python manage.py seed_tools --user-id 1    # Specific user
python manage.py seed_demo                 # Create demo data
```

---

## 10. Your First Task

Now you're ready to contribute! Here are good first issues:

### 🟢 Easy (Day 1-2)
1. **Create a management command** `seed_demo` that creates:
   - 2 users with preferences
   - 5 chat sessions per user
   - Some sample feedback
2. **Add a `duration` property** to `ChatSession` that returns time since creation
3. **Write unit tests** for `ChatSession.create_for_user()`

### 🟡 Medium (Week 1-2)
4. **Create a serializer + ViewSet** for `ChatSession` using the thin viewset pattern
5. **Create a serializer + ViewSet** for `MessageFeedback` with the `create_feedback` class method
6. **Add a management command** `cleanup_sessions` that archives sessions older than 90 days

### 🔴 Advanced (Week 3+)
7. **Create the chat endpoint** that connects Django → LangGraph → streaming response
8. **Implement document upload** API that triggers Celery task for pgvector processing
9. **Add WebSocket support** for real-time chat streaming

---

## 11. Troubleshooting

### "PGVECTOR_CONNECTION_STRING not found"
```bash
# Make sure Docker containers are running
docker compose up db redis -d
docker compose ps  # Should show "healthy"

# Make sure you have .env
cp .env.example .env
```

### "ModuleNotFoundError: No module named 'django'"
```bash
# You forgot to activate the virtual environment!
cd backend
source venv/bin/activate
```

### "Connection refused" on port 5433
```bash
# PostgreSQL isn't running or isn't healthy yet
docker compose logs db
docker compose restart db
# Wait 10 seconds after restart
```

### "Port 8000 already in use"
```bash
# Find what's using it
lsof -i :8000
# Kill it
kill -9 <PID>
# Or use a different port
python manage.py runserver 8001
```

### Migration errors
```bash
# Nuclear option — start fresh (DELETES ALL DATA)
docker compose down -v
docker compose up db redis -d
# Wait for healthy, then:
python manage.py migrate
python manage.py createsuperuser
```

---

## 12. Resources

### Must-Read
- [Django Official Tutorial](https://docs.djangoproject.com/en/stable/intro/tutorial01/)
- [Django REST Framework Quickstart](https://www.django-rest-framework.org/tutorial/quickstart/)
- [LangGraph Concepts](https://langchain-ai.github.io/langgraph/concepts/)

### Our Internal Docs
- [Django Lessons](../backend/docs/lessons/django/) — 10 detailed lessons
- [Model Architecture](../backend/apps/chatbot/models/MODEL_ARCHITECTURE.md)
- [Contributing Guide](./CONTRIBUTING.md)

### YouTube (Aparsoft)
- Tutorial series: **@aparsoft-ai**

---

> 💬 **Stuck?** Ask in the team Slack channel. No question is too basic — we all started somewhere!
