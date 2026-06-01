# LangGraph PostgreSQL Checkpointer — Production Implementation Guide

> **Audience:** Interns and developers working on the Aparsoft AI Chatbot project.
> This document covers how LangGraph persists conversation state to PostgreSQL,
> the architecture decisions we made, and the pitfalls to avoid.

---

## 📋 Table of Contents

1. [Why PostgreSQL for Checkpointing?](#1-why-postgresql-for-checkpointing)
2. [Architecture Overview](#2-architecture-overview)
3. [Installation & Prerequisites](#3-installation--prerequisites)
4. [Connection Strategies](#4-connection-strategies)
5. [Critical Configuration Constraints](#5-critical-configuration-constraints)
6. [Our Implementation](#6-our-implementation)
7. [Synchronous vs Asynchronous Flows](#7-synchronous-vs-asynchronous-flows)
8. [Security Best Practices](#8-security-best-practices)
9. [Troubleshooting Matrix](#9-troubleshooting-matrix)
10. [Testing the Checkpointer](#10-testing-the-checkpointer)

---

## 1. Why PostgreSQL for Checkpointing?

LangGraph agents are **stateful** — they need to remember conversation history, tool results, and intermediate reasoning across multiple turns. Without persistence, every server restart or process crash wipes all conversations.

The PostgreSQL checkpointer (`langgraph-checkpoint-postgres`) provides:

| Capability | Why It Matters |
|-----------|---------------|
| **Durability** | Conversation state survives server restarts and deploys |
| **Multi-turn persistence** | Users can resume a chat days later and pick up where they left off |
| **Horizontal scaling** | Multiple Django/Celery workers share the same state |
| **Time travel** | Replay or branch from any checkpoint in a conversation |
| **Auto-summarization** | Long conversations are compressed without losing context |

### What Django stores vs What LangGraph stores

```
┌─────────────────────────────────┐  ┌──────────────────────────────┐
│     Django Models (ORM)         │  │   LangGraph Checkpointer     │
│     PostgreSQL: chatbot_db      │  │   PostgreSQL: langchain_history│
├─────────────────────────────────┤  ├──────────────────────────────┤
│ ✓ Session titles & metadata     │  │ ✓ Actual chat messages        │
│ ✓ User preferences             │  │ ✓ Conversation state           │
│ ✓ Token usage & costs          │  │ ✓ Checkpoints (snapshots)      │
│ ✓ Message feedback             │  │ ✓ Automatic summaries          │
│ ✓ File upload metadata         │  │                                │
│ ✓ Tool configurations          │  │                                │
│ ✗ NOT messages!                │  │ ✗ NOT user preferences!        │
└─────────────────────────────────┘  └──────────────────────────────┘
```

We keep them separate by design — LangGraph's checkpointer is purpose-built for conversation state, so we don't duplicate it in Django models.

---

## 2. Architecture Overview

### How the pieces connect

```
User sends a message
        │
        ▼
┌──────────────────┐
│  Django ViewSet   │  ← Thin — validates input, calls service
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  AgentService    │  ← Creates orchestrator, invokes agent
└────────┬─────────┘
         │
         ▼
┌──────────────────────────────────────────────────┐
│  ChatAgentOrchestrator                           │
│  ┌──────────┐  ┌──────────┐  ┌────────────────┐ │
│  │   LLM    │→ │  Tools   │→ │ PostgresSaver  │ │
│  └──────────┘  └──────────┘  │ (ConnectionPool)│ │
│                              └────────┬─────────┘ │
└───────────────────────────────┼──────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │  PostgreSQL            │
                    │  langchain_history db  │
                    │  (checkpoints table)   │
                    └───────────────────────┘
```

### The three databases in our stack

| Database | Port | Purpose | Used by |
|----------|------|---------|----------|
| `chatbot_db` | 5434 | Django models (users, sessions, preferences) | Django ORM |
| `langchain_pgvector` | 5434 | Document embeddings for RAG | LangChain pgvector |
| `langchain_history` | 5434 | LangGraph checkpoints (conversation state) | PostgresSaver |

All three live in the same PostgreSQL instance (Docker container `chatbot-db`), just as separate databases.

---

## 3. Installation & Prerequisites

The official package relies on **Psycopg 3** with connection pooling:

```bash
pip install -U "psycopg[binary,pool]" langgraph-checkpoint-postgres
```

| Package | Why |
|---------|-----|
| `psycopg[binary]` | PostgreSQL adapter (pre-compiled, no libpq needed) |
| `psycopg[pool]` | Connection pooling support (`ConnectionPool`) |
| `langgraph-checkpoint-postgres` | The checkpointer itself |

Verify installation:

```bash
python -c "from langgraph.checkpoint.postgres import PostgresSaver; print('OK')"
python -c "from psycopg_pool import ConnectionPool; print('Pool OK')"
```

---

## 4. Connection Strategies

This is the most important section. **Choosing the wrong connection strategy is the #1 cause of checkpointer bugs.**

### Strategy A: Context Manager (Scripts & Notebooks Only)

Use this for short-lived scripts, Jupyter notebooks, or one-off commands:

```python
from langgraph.checkpoint.postgres import PostgresSaver

DB_URI = "postgresql://user:pass@localhost:5434/langchain_history?sslmode=disable"

with PostgresSaver.from_conn_string(DB_URI) as checkpointer:
    checkpointer.setup()  # Create tables on first run
    graph = builder.compile(checkpointer=checkpointer)
    result = graph.invoke({"messages": [...]}, config)
# ← Connection is automatically closed here
```

**⚠️ Do NOT use this in long-running processes.** The `with` block closes the connection when it exits. If you store the checkpointer outside the `with` block, you'll get `"the connection is closed"` errors.

### Strategy B: Connection Pool (Production — What We Use)

Use this for Django runserver, Celery workers, or any long-running process:

```python
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver

DB_URI = "postgresql://user:pass@localhost:5434/langchain_history?sslmode=disable"

pool = ConnectionPool(
    conninfo=DB_URI,
    min_size=2,          # Minimum connections kept open
    max_size=10,         # Maximum connections in the pool
    kwargs={
        "autocommit": True,
        "row_factory": dict_row,
    },
    open=True,           # Open connections immediately
)

checkpointer = PostgresSaver(pool)
checkpointer.setup()     # Create tables on first run
```

**Why a pool?**

| Problem | Single Connection | Connection Pool |
|---------|------------------|-----------------|
| Server closes idle connection | 💥 `"the connection is closed"` | ✅ Pool replaces it automatically |
| Network hiccup drops connection | 💥 Permanent failure | ✅ Pool reconnects transparently |
| Multiple concurrent requests | 💥 Serialized or errors | ✅ Pool serves them in parallel |
| Long-running process (hours/days) | 💥 Eventually breaks | ✅ Stays healthy indefinitely |

### Strategy C: Async with Connection Pool (FastAPI / ASGI)

For async applications, use `AsyncPostgresSaver` with `AsyncConnectionPool`:

```python
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

DB_URI = "postgresql://user:pass@localhost:5434/langchain_history?sslmode=disable"

async_pool = AsyncConnectionPool(
    conninfo=DB_URI,
    min_size=2,
    max_size=10,
    kwargs={"autocommit": True, "row_factory": dict_row},
    open=True,
)

async_checkpointer = AsyncPostgresSaver(async_pool)
await async_checkpointer.setup()
```

---

## 5. Critical Configuration Constraints

When building a PostgresSaver, three constraints must be honored to avoid runtime crashes:

### 1. Schema Initialization — Call `.setup()`

You **must** call `checkpointer.setup()` the first time the application runs against a fresh database. This creates the required tables (`checkpoints`, `checkpoint_writes`, `checkpoint_blobs`, `checkpoint_migrations`).

```python
checkpointer = PostgresSaver(pool)
checkpointer.setup()  # ← Required on first run; safe to call again (no-op)
```

### 2. Autocommit Must Be Enabled

All connections must use `autocommit=True`. Without this, schema setup changes may be silently rolled back, and checkpoint writes can fail.

```python
# ✅ Correct — in ConnectionPool kwargs
pool = ConnectionPool(
    conninfo=DB_URI,
    kwargs={"autocommit": True, "row_factory": dict_row},
)

# ✅ Correct — in manual connection
conn = psycopg.connect(DB_URI, autocommit=True, row_factory=dict_row)
```

### 3. Row Factory Must Be `dict_row`

The checkpointer accesses columns by name (e.g., `row["thread_id"]`). The default `tuple_row` causes `TypeError: tuple indices must be integers or slices, not str`.

```python
from psycopg.rows import dict_row

# ✅ Correct
pool = ConnectionPool(
    conninfo=DB_URI,
    kwargs={"autocommit": True, "row_factory": dict_row},
)

# ❌ Wrong — will crash at runtime
pool = ConnectionPool(conninfo=DB_URI)  # Missing dict_row!
```

---

## 6. Our Implementation

### The Singleton Pattern (Pool-Backed)

We use a **singleton** backed by a `ConnectionPool` so that every part of the application shares one pool:

```python
# backend/apps/chatbot/services/agent_service.py

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver

_pool: Optional[ConnectionPool] = None
_checkpointer: Optional[PostgresSaver] = None


def get_checkpointer() -> PostgresSaver:
    """Return a PostgresSaver backed by a ConnectionPool singleton."""
    global _pool, _checkpointer
    if _checkpointer is None:
        _pool = ConnectionPool(
            conninfo=settings.PG_CHECKPOINT_URI,
            min_size=2,
            max_size=10,
            kwargs={"autocommit": True, "row_factory": dict_row},
            open=True,
        )
        _checkpointer = PostgresSaver(_pool)
        _checkpointer.setup()
    return _checkpointer
```

### Why a Singleton?

- **Connection pools are expensive** — creating one per request would exhaust database connections
- **The pool auto-heals** — if a connection drops, the pool replaces it transparently
- **Thread-safe** — `ConnectionPool` handles concurrent access internally
- **Shared across services** — both `AgentService` and `MessageService` use the same pool

### How Other Services Use It

```python
# backend/apps/chatbot/services/message_service.py

class MessageService:
    @staticmethod
    def _get_checkpointer() -> PostgresSaver:
        """Delegate to the shared pool-backed singleton."""
        from .agent_service import get_checkpointer
        return get_checkpointer()
```

### The Connection URI

The `PG_CHECKPOINT_URI` setting in `.env` must point to the `langchain_history` database:

```bash
# .env — matches Docker Compose configuration
PG_CHECKPOINT_URI=postgresql://chatbot_user:chatbot_pass@localhost:5434/langchain_history?sslmode=disable
```

Key points:
- **Port 5434** — Docker maps container port 5432 to host port 5434
- **Database `langchain_history`** — created by `docker/init-db.sh`
- **`sslmode=disable`** — local development doesn't use SSL

---

## 7. Synchronous vs Asynchronous Flows

### Synchronous (Django Views, Celery Tasks, Management Commands)

This is what we use. The `PostgresSaver` class is synchronous:

```python
from chatbot.services import AgentService

result = AgentService.chat(session, "What is LangGraph?")
# → Uses PostgresSaver with ConnectionPool under the hood
```

### Asynchronous (FastAPI, ASGI, Django Async Views)

For async applications, use `AsyncPostgresSaver` with `AsyncConnectionPool`:

```python
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

async_pool = AsyncConnectionPool(
    conninfo=DB_URI,
    min_size=2,
    max_size=10,
    kwargs={"autocommit": True, "row_factory": dict_row},
    open=True,
)

async_checkpointer = AsyncPostgresSaver(async_pool)
await async_checkpointer.setup()

# Use with an async graph
graph = builder.compile(checkpointer=async_checkpointer)
result = await graph.ainvoke({"messages": [...]}, config)
```

> **Note:** Do not mix sync and async checkpointers. Use `PostgresSaver` for sync code and `AsyncPostgresSaver` for async code.

---

## 8. Security Best Practices

### Environment Variable: `LANGGRAPH_STRICT_MSGPACK`

To protect against potential remote code execution (RCE) vectors if the database is ever compromised, set this environment variable in all environments:

```bash
LANGGRAPH_STRICT_MSGPACK=true
```

This restricts state deserialization to only known-safe types.

### Connection String Security

- **Never commit `.env` files** to version control (already in `.gitignore`)
- Use `sslmode=require` for production (managed Postgres on DigitalOcean, AWS RDS, etc.)
- Rotate database credentials periodically
- Use separate database users for the application vs. admin tasks

### Network Security

- In production, the database should not be publicly accessible
- Use Docker networks or VPC security groups to restrict access
- The `langchain_history` database should only be accessible from the application servers

---

## 9. Troubleshooting Matrix

### Connection Errors

| Error | Root Cause | Fix |
|-------|-----------|-----|
| `InterfaceError: the connection is closed` | Using a single `Connection` that was dropped (idle timeout, network issue, server restart). The connection cannot recover. | Use a `ConnectionPool` instead of a single connection. The pool automatically replaces broken connections. |
| `ConnectionRefusedError` | PostgreSQL is not running or not reachable on the specified host/port. | Verify Docker is running: `docker compose ps`. Check that `PG_CHECKPOINT_URI` uses the correct port (5434 for Docker). |
| `OperationalError: FATAL: database "langchain_history" does not exist` | The database hasn't been created yet. | Run `docker compose up db -d` and wait for it to be healthy. The `init-db.sh` script creates the database automatically. |
| `OperationalError: FATAL: password authentication failed` | Wrong credentials in `PG_CHECKPOINT_URI`. | Verify the username, password, and database name match your Docker Compose configuration. |

### Schema & Migration Errors

| Error | Root Cause | Fix |
|-------|-----------|-----|
| `ProgrammingError: relation "checkpoints" does not exist` | `checkpointer.setup()` was never called, so the required tables don't exist. | Call `checkpointer.setup()` once after creating the checkpointer. It's safe to call multiple times (no-op if tables exist). |
| `TypeError: tuple indices must be integers or slices, not str` | The connection was created without `row_factory=dict_row`. The checkpointer accesses columns by name, but the default `tuple_row` returns positional tuples. | Always pass `row_factory=dict_row` in your connection kwargs: `kwargs={"autocommit": True, "row_factory": dict_row}`. |
| Schema changes disappear across restarts | `setup()` was called without `autocommit=True`, so the table creation was rolled back. | Ensure `autocommit=True` is set on all connections. With `ConnectionPool`, pass it in `kwargs`. |

### Pool-Specific Issues

| Error | Root Cause | Fix |
|-------|-----------|-----|
| `PoolError: connection pool is full` | All pool connections are in use and `max_size` is reached. | Increase `max_size` or reduce concurrent request count. Default `max_size=10` handles most workloads. |
| `PoolError: the pool is closed` | The pool was explicitly closed or the process is shutting down. | Don't close the pool during normal operation. It should live for the process lifetime. |
| Slow first request after idle period | Pool connections were closed by PostgreSQL's `idle_session_timeout`. | Set `min_size=2` (or higher) to keep warm connections. The pool will reconnect as needed. |

### URI Configuration Errors

| Error | Root Cause | Fix |
|-------|-----------|-----|
| `sslmode` parameter not recognized | The URI has a malformed query string (e.g., `?sslmode` without a value). | Use `?sslmode=disable` (local) or `?sslmode=require` (production). Never use bare `?sslmode`. |
| `postgresql+psycopg://` scheme | SQLAlchemy uses `postgresql+psycopg://` but raw psycopg (used by LangGraph) expects `postgresql://`. | The `PG_CHECKPOINT_URI` must use `postgresql://` (not `postgresql+psycopg://`). Our settings module auto-corrects this. |
| Wrong port in URI | Using port 5432 (container internal) instead of 5434 (host-mapped). | Docker Compose maps container port 5432 to host port 5434. Use `localhost:5434` in the URI. |

---

## 10. Testing the Checkpointer

### Quick Smoke Test

Verify the checkpointer connects and creates tables:

```bash
cd backend
source venv/bin/activate

python manage.py shell --settings=config.settings.development
```

```python
from chatbot.services.agent_service import get_checkpointer

checkpointer = get_checkpointer()
print(type(checkpointer))  # <class 'langgraph.checkpoint.postgres.PostgresSaver'>
print("Checkpointer OK!")
```

### Test with the Management Command

```bash
python manage.py run_chat --message "What is LangGraph?" --model gpt-4o-mini
```

If you see `[INFO] PostgresSaver checkpointer initialised (pool-backed)` followed by a response, everything is working.

### Verify Database Tables

```bash
docker exec chatbot-db psql -U chatbot_user -d langchain_history -c "\dt"
```

You should see these tables:
```
checkpoints
checkpoint_writes
checkpoint_blobs
checkpoint_migrations
```

### Unit Tests

All checkpointer tests are mocked (no real database required). See:

```bash
python manage.py test chatbot.tests.test_agent_service.TestCheckpointer \
    --settings=config.settings.test -v 2
```

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────────────┐
│              LANGGRAPH CHECKPOINTER CHEAT SHEET                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  PRODUCTION (long-running):                                        │
│    pool = ConnectionPool(conninfo=URI, min_size=2, max_size=10,    │
│                           kwargs={"autocommit": True,               │
│                                    "row_factory": dict_row})        │
│    checkpointer = PostgresSaver(pool)                               │
│    checkpointer.setup()                                             │
│                                                                     │
│  SCRIPTS / NOTEBOOKS (short-lived):                                │
│    with PostgresSaver.from_conn_string(URI) as checkpointer:        │
│        checkpointer.setup()                                         │
│        graph = builder.compile(checkpointer=checkpointer)           │
│                                                                     │
│  THREE RULES:                                                       │
│    1. Always call .setup() on first run                             │
│    2. Always use autocommit=True                                    │
│    3. Always use row_factory=dict_row                               │
│                                                                     │
│  NEVER:                                                             │
│    ✗ Store a from_conn_string() checkpointer outside the with block│
│    ✗ Use a single Connection in long-running processes              │
│    ✗ Forget sslmode= in the URI                                     │
│    ✗ Use postgresql+psycopg:// (use postgresql://)                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```


