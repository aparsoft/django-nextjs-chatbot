# 🚀 Quick Start Guide

> **Django, Celery, and Next.js run locally** — only Postgres and Redis are Dockerized.
> This is how Django devs generally work: hot-reload, `pdb` breakpoints, real stack traces.

---

## Setup (5 minutes)

### 1. Clone & configure

```bash
git clone https://github.com/aparsoft/django-nextjs-chatbot.git
cd django-nextjs-chatbot

# Create your .env from the template
cp .env.example .env
# Edit .env → add your OPENAI_API_KEY
```

### 2. Start infrastructure (Docker)

```bash
docker compose up -d

# Verify both services are healthy
docker compose ps
# Should show: chatbot-db (healthy), chatbot-redis (healthy)
```

This creates **three databases** automatically:
- `chatbot_db` — Django models
- `langchain_pgvector` — pgvector embeddings for RAG
- `langchain_history` — LangGraph checkpoints

### 3. Backend (local)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Linux/Mac
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### 4. Celery workers (local, separate terminals)

```bash
# Terminal 2 — worker
cd backend && source venv/bin/activate
celery -A config worker --loglevel=info

# Terminal 3 — beat scheduler
cd backend && source venv/bin/activate
celery -A config beat --loglevel=info
```

### 5. Frontend (local, separate terminal)

```bash
# Terminal 4
cd frontend
npm install
npm run dev
```

---

## Access Your Application

| Service | URL | Credentials |
|---------|-----|-------------|
| **Frontend** | http://localhost:3000 | — |
| **Backend API** | http://localhost:8000/api/v1/ | — |
| **Django Admin** | http://localhost:8000/chatbot-admin/ | (your superuser) |
| **PostgreSQL** | localhost:**5433** | chatbot_user / chatbot_pass |
| **Redis** | localhost:**6380** | — |

---

## Common Commands

### Infrastructure (Docker)

```bash
docker compose up -d           # Start Postgres + Redis
docker compose down            # Stop
docker compose down -v         # Stop + wipe volumes (fresh start)
docker compose logs -f db      # Follow Postgres logs
docker compose ps              # Check service health
```

### Backend (local)

```bash
cd backend && source venv/bin/activate

python manage.py runserver                  # Start dev server
python manage.py migrate                    # Apply migrations
python manage.py makemigrations chatbot     # Generate migrations
python manage.py shell                      # Interactive Django shell
python manage.py createsuperuser            # Create admin user
python manage.py test apps.chatbot          # Run tests
```

### Celery (local, separate terminals)

```bash
cd backend && source venv/bin/activate

celery -A config worker --loglevel=info     # Worker
celery -A config beat --loglevel=info       # Beat scheduler
celery -A config inspect active             # Check active tasks
```

### Frontend (local)

```bash
cd frontend
npm run dev          # Dev server
npm run build        # Production build
npm run lint         # Lint check
```

---

## Your Daily Workflow

```
Terminal 1:  docker compose up -d                      # Postgres + Redis
Terminal 2:  cd backend && python manage.py runserver   # Django
Terminal 3:  celery -A config worker --loglevel=info    # Background jobs
Terminal 4:  celery -A config beat --loglevel=info      # Scheduler
Terminal 5:  cd frontend && npm run dev                 # Next.js
```

---

## Troubleshooting

### "PGVECTOR_CONNECTION_STRING not found"
```bash
# Make sure Docker containers are running
docker compose up -d
docker compose ps  # Both should show "healthy"
```

### "ModuleNotFoundError: No module named 'django'"
```bash
# You forgot to activate the virtual environment!
cd backend && source venv/bin/activate
```

### "Connection refused" on port 5433
```bash
# Postgres isn't healthy yet — wait 10 seconds
docker compose logs db
docker compose restart db
```

### Port 8000 already in use
```bash
lsof -i :8000          # Find what's using it
kill -9 <PID>          # Kill it
# Or use a different port:
python manage.py runserver 8001
```

### Fresh start (wipe all data)
```bash
docker compose down -v             # Delete volumes
docker compose up -d               # Recreate everything
cd backend && source venv/bin/activate
python manage.py migrate
python manage.py createsuperuser
```

---

## Need Help?

- 📘 [Intern Onboarding Guide](./docs/INTERN_ONBOARDING.md) — day-by-day walkthrough
- 🤝 [Contributing Guide](./docs/CONTRIBUTING.md) — Git workflow & code style
- 📺 [YouTube Tutorials](https://youtube.com/@aparsoft-ai) — step-by-step videos
- 🐛 [GitHub Issues](https://github.com/aparsoft/django-nextjs-chatbot/issues) — report bugs

---

*Built with ❤️ by Aparsoft Team*
