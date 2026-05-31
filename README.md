# 🤖 Learn AI Chatbots | Django + Next.js
*Educational Tutorial Series for Developers*

[![YouTube](https://img.shields.io/badge/YouTube-Subscribe-red?style=flat&logo=youtube)](https://youtube.com/@aparsoft)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Follow-blue?style=flat&logo=linkedin)](https://linkedin.com/company/aparsoft)
[![Website](https://img.shields.io/badge/Website-aparsoft.com-green?style=flat)](https://aparsoft.com)

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)
![Django](https://img.shields.io/badge/Django-5.2-green?logo=django)
![Next.js](https://img.shields.io/badge/Next.js-15-black?logo=next.js)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-blue?logo=postgresql)
![LangChain](https://img.shields.io/badge/LangChain-Latest-green)

> **🎓 Educational Tutorial Series for the Developer Community**
>
> Learn how to build conversational AI chatbots from scratch using Django, Django REST Framework, and Next.js. This hands-on tutorial introduces you to LangChain and LangGraph basics while building a real working chatbot.

## 📖 What Is This Project?

This is a **learning-focused repository** designed to teach developers how to integrate AI into full-stack web applications. It's NOT a comprehensive enterprise solution - it's a clear, straightforward tutorial on building your first conversational chatbot.

**What You'll Learn:**
- Setting up Django + Django REST Framework for AI applications
- Building a modern frontend with Next.js
- Creating basic conversational chatbot functionality
- Introduction to LangChain fundamentals
- LangGraph basics for conversation flows
- Connecting Django backend with AI services
- Deploying a simple AI chatbot

---

## ⚡ Quick Start

### Option 1: Docker (Recommended)

```bash
# 1. Clone the repo
git clone https://github.com/aparsoft/django-nextjs-chatbot.git
cd django-nextjs-chatbot

# 2. Create .env file and add your OpenAI API key
cp .env.example .env
# Edit .env → set OPENAI_API_KEY=sk-proj-...

# 3. Start everything
docker-compose up --build
```

That's it! Everything auto-configures:
- ✅ PostgreSQL 17 + pgvector extension installed
- ✅ Three databases created: `chatbot_db`, `langchain_pgvector`, `langchain_history`
- ✅ Database migrations run automatically
- ✅ Superuser created (`admin` / `admin123`)
- ✅ Static files collected
- ✅ All services start and connect

### Option 2: Run Backend Locally (for development)

```bash
# 1. Start only infrastructure
docker-compose up db redis -d

# 2. Set up backend
cd backend
python -m venv venv
source venv/bin/activate    # Linux/Mac
# venv\Scripts\activate     # Windows
pip install -r requirements.txt

# 3. Configure environment
cp ../.env.example ../.env.local
# Edit .env.local → set your OPENAI_API_KEY

# 4. Run migrations & start
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Access Your Application

| Service | URL | Credentials |
|---------|-----|-------------|
| **Frontend** | http://localhost:3000 | — |
| **Backend API** | http://localhost:8000/api/v1/ | — |
| **Django Admin** | http://localhost:8000/chatbot-admin/ | admin / admin123 |
| **PostgreSQL** | localhost:**5433** | chatbot_user / chatbot_pass |
| **Redis** | localhost:**6380** | — |

### 📚 Intern Onboarding

New to the project? Start here:

| Document | What It Covers |
|----------|---------------|
| [📘 Intern Onboarding Guide](./docs/INTERN_ONBOARDING.md) | Day-by-day setup → first contribution |
| [🤝 Contributing Guide](./docs/CONTRIBUTING.md) | Git workflow, PRs, code style |
| [🏗️ Model Architecture](./backend/apps/chatbot/models/MODEL_ARCHITECTURE.md) | 8 Django models, fatty model pattern |
| [📖 Django Lessons](./backend/docs/lessons/django/) | 10 in-depth Django tutorials |

---

## 🛠️ Tech Stack

### Backend (Django 5.2)
- **Django 5.2** + **Django REST Framework** — API development
- **PostgreSQL 17 + pgvector** — relational DB with vector similarity search
- **Redis 7** — cache, Celery broker, Django Channels
- **Celery + Celery Beat** — background task processing & scheduling
- **LangChain** — LLM application framework
- **LangGraph** — stateful multi-step conversation flows with PostgresCheckpointer

### Frontend (Next.js 15)
- **Next.js 15** + **React 19** — server-side rendered UI
- **Tailwind CSS** — utility-first styling
- **Axios** — HTTP client

### AI/ML
- **OpenAI GPT** — chat completions, embeddings
- **pgvector** — vector similarity search for RAG
- **LangGraph PostgresSaver** — conversation checkpoint persistence

### Infrastructure
- **Docker Compose** — multi-container orchestration with health checks
- **pgvector/pgvector:pg17** — PostgreSQL image with pgvector pre-installed

---

## 📊 System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Docker Compose                           │
│                                                              │
│  ┌──────────┐     ┌──────────────────────────────────┐      │
│  │  Next.js │────▶│         Django Backend            │      │
│  │  :3000   │     │         :8000                     │      │
│  └──────────┘     │  ┌────────────┐ ┌─────────────┐  │      │
│                   │  │  Celery     │ │ Celery Beat │  │      │
│                   │  │  (worker)   │ │ (scheduler)  │  │      │
│                   │  └────────────┘ └─────────────┘  │      │
│                   └──────────┬───────────────────────┘      │
│                              │                               │
│              ┌───────────────┼───────────────┐               │
│              ▼               ▼               ▼               │
│  ┌──────────────────┐ ┌───────────┐ ┌──────────────┐        │
│  │ PostgreSQL 17    │ │  Redis 7  │ │  OpenAI API  │        │
│  │ + pgvector       │ │  :6380    │ │  (external)  │        │
│  │ :5433            │ │           │ │              │        │
│  │                  │ │ • cache   │ │ • GPT models │        │
│  │ • chatbot_db     │ │ • broker  │ │ • embeddings │        │
│  │ • langchain_     │ │ • channels│ │              │        │
│  │   pgvector       │ │           │ │              │        │
│  │ • langchain_     │ │           │ │              │        │
│  │   history        │ │           │ │              │        │
│  └──────────────────┘ └───────────┘ └──────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

### Database Architecture

We use a **single PostgreSQL instance with three separate databases**:

| Database | Purpose | Used By |
|----------|---------|---------|
| `chatbot_db` | Django models (users, sessions, preferences, tokens, feedback) | Django ORM |
| `langchain_pgvector` | Document embeddings + vector similarity search | LangChain PGVector |
| `langchain_history` | LangGraph checkpoints (conversation state, messages) | LangGraph PostgresSaver |

All three are created automatically by `docker/init-db.sh` on first startup.

---

## 🎯 Django Model Architecture (8 Models)

We follow the **"Fatty Models, Thin Viewsets"** pattern — business logic lives in model methods, not in views.

```
CustomUser (accounts app)
    │
    ├── ChatSession (1:N)         ← Maps to LangGraph thread_id
    │   ├── TokenUsage (1:N)      ← Token costs per request
    │   ├── MessageFeedback (1:N) ← User ratings on AI responses
    │   └── UserDocument (1:N)    ← RAG file uploads (pgvector refs)
    │
    ├── UserPreference (1:1)      ← AI settings & defaults
    ├── UserTool (1:N)            ← Tool enable/disable + config
    └── UserAPIKey (1:N)          ← Encrypted provider API keys

SystemPromptTemplate (standalone) ← Reusable system prompts
```

**Key principle:** Django stores metadata (titles, settings, analytics). LangGraph stores actual messages. pgvector stores embeddings. No duplication!

📖 Full details: [MODEL_ARCHITECTURE.md](./backend/apps/chatbot/models/MODEL_ARCHITECTURE.md)

---

## 🎬 YouTube Tutorial Series

This repository is the companion code for our **beginner-friendly video tutorial series**!

### 📺 Complete Tutorial Playlist

**Part 1: Setup & Basics**
- "Introduction: What We're Building"
- "Django + Next.js Setup from Scratch"
- "Your First API Call to OpenAI"

**Part 2: Building the Chatbot**
- "Creating the Django REST API"
- "Next.js Frontend Setup"
- "Connecting Frontend to Backend"

**Part 3: Adding Intelligence**
- "Introduction to LangChain"
- "Basic Conversation Memory"
- "Introduction to LangGraph"

**Part 4: Deployment**
- "Docker Basics for Beginners"
- "Deploying Your First Chatbot"

**[→ Start Learning on YouTube](https://youtube.com/@aparsoft-ai)**

---

## 🤝 Contributing

We welcome contributions from developers at all levels!

| Resource | Link |
|----------|------|
| 📘 Intern Onboarding | [docs/INTERN_ONBOARDING.md](./docs/INTERN_ONBOARDING.md) |
| 🤝 Contributing Guide | [docs/CONTRIBUTING.md](./docs/CONTRIBUTING.md) |
| 🏗️ Model Architecture | [backend/apps/chatbot/models/MODEL_ARCHITECTURE.md](./backend/apps/chatbot/models/MODEL_ARCHITECTURE.md) |
| 📖 Django Lessons (10) | [backend/docs/lessons/django/](./backend/docs/lessons/django/) |

**Not sure where to start?** Check the [Contributing Guide](./docs/CONTRIBUTING.md) for the complete Git workflow and first-task suggestions!

---

## 📞 Get Help & Connect

- **YouTube:** [@aparsoft-ai](https://youtube.com/@aparsoft-ai)
- **LinkedIn:** [/company/aparsoft](https://linkedin.com/company/aparsoft)
- **GitHub Issues:** [Report bugs here](https://github.com/aparsoft/django-nextjs-chatbot/issues)
- **Website:** [aparsoft.com](https://aparsoft.com)

---

## 📄 License

Copyright © 2024 Aparsoft Private Limited. All rights reserved.

This code is provided for educational purposes. Feel free to learn from it, modify it, and use it in your own projects!

---

*Built with ❤️ by the Aparsoft Team in Bengaluru, India*
