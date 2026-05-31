# System Setup & Configuration

### For WSL2 Specifically:

Create/edit `.wslconfig` in Windows:
```ini
# Location: C:\Users\YourUsername\.wslconfig
[wsl2]
kernelCommandLine = sysctl.vm.overcommit_memory=1
memory=8GB
processors=4
```

Then restart WSL from PowerShell:
```powershell
wsl --shutdown
```

---

## Default Superuser Credentials

The system automatically creates a Django superuser on first startup:

- **Username:** `admin`
- **Email:** `admin@aparsoft.com`
- **Password:** `admin123`

### Security Notice

⚠️ **IMPORTANT:** The default password is for development only!

**For Production:**
1. Change the password immediately:
   ```bash
   docker-compose exec backend python manage.py changepassword admin
   ```

2. Or create a new superuser:
   ```bash
   docker-compose exec backend python manage.py createsuperuser
   ```

3. Delete the default admin user:
   ```bash
   docker-compose exec backend python manage.py shell
   >>> from django.contrib.auth import get_user_model
   >>> User = get_user_model()
   >>> User.objects.get(username='admin').delete()
   ```

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Load Balancer / Nginx                │
│                    (Future Production)                  │
└─────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌──────────────┐
│   Next.js     │   │    Django     │   │   Django     │
│   Frontend    │──▶│   Backend     │   │    Admin     │
│   :3000       │   │   :8000       │   │   Panel      │
└───────────────┘   └───────────────┘   └──────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌──────────────┐
│  PostgreSQL   │   │     Redis     │   │   Celery     │
│   :5433       │   │    :6380      │   │   Workers    │
│  (Database)   │   │   (Cache)     │   │ (Background) │
└───────────────┘   └───────────────┘   └──────────────┘
                                                │
                                        ┌──────────────┐
                                        │ Celery Beat  │
                                        │ (Scheduler)  │
                                        └──────────────┘
```

---

## Container Details

| Service | Container Name | Internal Port | External Port | Purpose |
|---------|---------------|---------------|---------------|---------|
| PostgreSQL | chatbot-db | 5432 | 5433 | Main database |
| Redis | chatbot-redis | 6379 | 6380 | Cache & message broker |
| Django | chatbot-backend | 8000 | 8000 | API & admin |
| Next.js | chatbot-frontend | 3000 | 3000 | User interface |
| Celery Worker | chatbot-celery | - | - | Background tasks |
| Celery Beat | chatbot-celery-beat | - | - | Scheduled tasks |

---

## Environment Variables Reference

### Required
- `OPENAI_API_KEY` - Your OpenAI API key (required for AI features)
- `DB_NAME` - Database name (default: chatbot_db)
- `DB_USER` - Database user (default: chatbot_user)
- `DB_PASSWORD` - Database password (default: chatbot_pass)

### Optional
- `TAVILY_API_KEY` - For web search capabilities
- `ANTHROPIC_API_KEY` - For Claude AI features
- `DJANGO_SECRET_KEY` - Django secret key (auto-generated in dev)

---

## Accessing Services

### Django Admin Panel
- **URL:** http://localhost:8000/chatbot-admin/
- **Username:** admin
- **Password:** admin123

**Features:**
- User management
- Database models admin
- Site configuration
- Celery task monitoring
- System logs

### PostgreSQL Database
Connect from your host machine:
```bash
psql -h localhost -p 5433 -U chatbot_user -d chatbot_db
# Password: chatbot_pass
```

Or using database tools (DBeaver, pgAdmin):
- Host: localhost
- Port: 5433
- Database: chatbot_db
- Username: chatbot_user
- Password: chatbot_pass

### Redis Cache
```bash
redis-cli -h localhost -p 6380
```

---

## Development Workflow

### 1. Making Database Changes

```bash
# Create migrations
docker-compose exec backend python manage.py makemigrations

# Apply migrations
docker-compose exec backend python manage.py migrate

# View migration status
docker-compose exec backend python manage.py showmigrations
```

### 2. Managing Static Files

```bash
# Collect static files
docker-compose exec backend python manage.py collectstatic --noinput

# Clear cache
docker-compose exec backend python manage.py clearcache
```

### 3. Django Shell Access

```bash
# Python shell with Django context
docker-compose exec backend python manage.py shell

# Database shell
docker-compose exec backend python manage.py dbshell
```

### 4. Celery Management

```bash
# View active workers
docker-compose exec celery celery -A config inspect active

# View scheduled tasks
docker-compose exec celery celery -A config inspect scheduled

# Purge all tasks
docker-compose exec celery celery -A config purge
```

---

## Performance Tuning

### PostgreSQL
- Current: Default settings
- For production: Adjust `shared_buffers`, `work_mem`, etc.

### Redis
- Current: No persistence (development)
- For production: Enable AOF or RDB persistence

### Celery
- Current: Default concurrency
- Adjust `CELERY_CONCURRENCY` in `.env` for production

---

## Backup & Restore

### Database Backup
```bash
# Backup
docker-compose exec db pg_dump -U chatbot_user chatbot_db > backup_$(date +%Y%m%d).sql

# Restore
cat backup_20251002.sql | docker-compose exec -T db psql -U chatbot_user chatbot_db
```

### Full System Backup
```bash
# Backup volumes
docker-compose down
sudo tar -czf backup_volumes.tar.gz /var/lib/docker/volumes/django-nextjs-chatbot_*

# Restore
sudo tar -xzf backup_volumes.tar.gz -C /
```

---

## Monitoring

### View Real-time Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f celery
```

### Container Stats
```bash
docker stats
```

### Health Checks
- Backend: http://localhost:8000/health/
- Database: Automatic health check in docker-compose
- Redis: Automatic health check in docker-compose

---

## Troubleshooting

### Container Won't Start
```bash
# View detailed logs
docker-compose logs [service-name]

# Restart specific service
docker-compose restart [service-name]

# Rebuild and restart
docker-compose up --build [service-name]
```

### Database Issues
```bash
# Reset database (⚠️ DELETES ALL DATA)
docker-compose down -v
docker-compose up --build
```

### Permission Issues
```bash
# Fix file permissions
sudo chown -R $USER:$USER .
```

---

**For more help:** See [QUICK_START.md](./QUICK_START.md) or visit our [YouTube channel](https://youtube.com/@aparsoft-ai)
