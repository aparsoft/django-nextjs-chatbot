# Docker Installation Guide

Complete setup guide for installing Docker on WSL 2 Ubuntu 24.04.

## 🐳 Installing Docker on WSL 2 (Ubuntu 24.04)

### Step 1: Update System Packages

```bash
sudo apt update
sudo apt upgrade -y
```

### Step 2: Install Prerequisites

```bash
sudo apt install -y ca-certificates curl gnupg lsb-release
```

### Step 3: Add Docker's Official GPG Key

```bash
sudo install -m 0755 -d /etc/apt/keyrings

curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

sudo chmod a+r /etc/apt/keyrings/docker.gpg
```

### Step 4: Set Up Docker Repository

```bash
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
```

### Step 5: Install Docker Engine

```bash
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

### Step 6: Start Docker Service

```bash
sudo service docker start
```

### Step 7: Verify Installation

```bash
sudo docker run hello-world
```

You should see: "Hello from Docker!" message.

### Step 8: Add Your User to Docker Group (Optional but Recommended)

This allows you to run Docker without sudo:

```bash
sudo usermod -aG docker $USER
```

**Important:** After this, you need to log out and log back in, or run:

```bash
newgrp docker
```

docker compose version
```

You should see something like: Docker Compose version v2.x.x

---

## 2️⃣ Quick Start: Run the Project

### 1. Set Up Environment Variables

**Backend:**
```bash
cd backend
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

**Frontend:**
```bash
cd frontend
cp .env.example .env.local
# Review the settings (defaults should work)
```

**Root .env (for docker-compose):**
```bash
# Create .env in project root
echo "OPENAI_API_KEY=your-actual-openai-key-here" > .env
```

### 2. Build and Run
```bash
# From project root
docker compose up --build
```

This will:
- Create PostgreSQL database container
- Build and run Django backend on `http://localhost:8000`
- Build and run Next.js frontend on `http://localhost:3000`

### 3. Run Migrations (First Time Only)
```bash
docker compose exec backend python manage.py migrate
```

### 4. Create Superuser (Optional)
```bash
docker compose exec backend python manage.py createsuperuser
```

### 5. Access the Application
- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **Django Admin:** http://localhost:8000/admin

---

## 3️⃣ Common Docker Commands

| Task | Command |
|------|---------|
| Start all services | `docker compose up` |
| Start in background | `docker compose up -d` |
| Stop all services | `docker compose down` |
| View logs | `docker compose logs -f` |
| Rebuild after changes | `docker compose up --build` |
| Run Django migrations | `docker compose exec backend python manage.py migrate` |
| Access DB | `docker compose exec db psql -U chatbot_user -d chatbot_db` |
| Install frontend package | `docker compose exec frontend npm install <package>` |
| Run frontend build | `docker compose exec frontend npm run build` |

---

## 4️⃣ Best Practices for 2026

### Multi-Stage Dockerfiles
- Use multi-stage builds for both backend and frontend to keep images small and secure.

### .dockerignore Example
Create a `.dockerignore` in both backend and frontend:
```
# .dockerignore
node_modules
.next
*.log
.env
__pycache__/
*.pyc
.git
Dockerfile*
```bash
README.md
docker-compose up --build
```

### Security Checklist
- Use non-root users in containers
- Keep images updated regularly
- Scan images for vulnerabilities
- Use secrets management for sensitive data
- Enable SSL/TLS (Let’s Encrypt for production)
- Never commit `.env` files to version control
- Use environment variables for config

### Health Checks
- Both backend and db services should have healthchecks in `docker-compose.yml`.

### Backups
- Use a cron job or script to backup your database and media files regularly.

Example (PostgreSQL):
```bash
docker compose exec db pg_dump -U chatbot_user chatbot_db | gzip > ./backups/db_$(date +%Y%m%d_%H%M%S).sql.gz
```

---

## 5️⃣ Development Workflow

1. **Edit code** – Changes auto-reload for both Django and Next.js
2. **Backend changes** – Auto-reload with Django’s runserver
3. **Frontend changes** – Hot Module Replacement (HMR) with Next.js
4. **New dependencies:**
    - Backend: Add to `requirements.txt`, then `docker compose up --build`
    - Frontend: `docker compose exec frontend npm install <package>`

---

## 6️⃣ Production Deployment (Overview)

- Use separate `Dockerfile.prod` and `docker-compose.prod.yml`
- Set `DEBUG=0` and a strong `SECRET_KEY`
- Serve static files with Nginx
- Use Gunicorn for Django
- Use a managed database for reliability
- Set up monitoring and logging

---

## 7️⃣ FAQ & Troubleshooting

**Q: Docker says port is already in use?**
A: Change the port mapping in `docker-compose.yml` (e.g., `3000:3000` → `3001:3000`).

**Q: Frontend hot reload not working?**
A: Uncomment `WATCHPACK_POLLING` in `docker-compose.yml` or add `WATCHPACK_POLLING=true` to `frontend/.env.local`.

**Q: Database connection issues?**
A: Wait for the database to be ready. If issues persist, try `docker compose restart backend`.

**Q: Permission denied errors?**
A: Fix file permissions: `sudo chown -R $USER:$USER .`

**Q: How do I clear Docker build cache?**
A: `docker compose build --no-cache`

**Q: WSL2 memory limits?**
A: Edit `.wslconfig` in Windows user folder:
```ini
[wsl2]
```
processors=4
swap=2GB
```
Then restart WSL: `wsl --shutdown`

---

## ✅ Final Checklist

- [ ] Docker and Docker Compose installed
- [ ] `.env` files set up for backend, frontend, and root
- [ ] `docker compose up --build` runs without errors
- [ ] Can access frontend and backend in browser

---

**Need help?**
- Check out our [YouTube tutorials](https://youtube.com/@aparsoft-ai)
- Ask in GitHub Discussions
- Or reach out to a team member!

---

