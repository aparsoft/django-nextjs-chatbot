# Docker Installation Guide

Complete setup guide for installing Docker and running the project. Choose your platform below.

---

## 🪟 Option A: Docker Desktop on Windows (Recommended for Windows users)

Docker Desktop includes Docker Engine, Docker Compose, and a GUI. It uses WSL 2 under the hood.

### Step 1: Install WSL 2

Open **PowerShell as Administrator**:

```powershell
wsl --install
```

This installs WSL 2 with Ubuntu by default. **Restart your computer** after this completes.

### Step 2: Set up Ubuntu

```powershell
# Launch Ubuntu (first launch takes a minute)
wsl

# Inside Ubuntu, update packages
sudo apt update && sudo apt upgrade -y
```

### Step 3: Install Docker Desktop

1. Download from [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/)
2. Run the installer — ensure **"Use WSL 2 instead of Hyper-V"** is checked
3. After installation, launch Docker Desktop
4. Go to **Settings → Resources → WSL Integration** — enable integration with your Ubuntu distro
5. Docker is now available inside WSL automatically

### Step 4: Verify in WSL

```bash
# Open WSL terminal
wsl

# Optional: Just to Verify Docker works
docker --version
docker compose version
docker run hello-world
```

✅ You should see: `Hello from Docker!` and version info for Docker + Compose.

### Step 5: Configure Git in WSL

```bash
# Install Git (if not already present)
sudo apt install git -y

# Configure your identity
git config --global user.name "Your Full Name"
git config --global user.email "you@example.com"
git config --global core.autocrlf input
```

> 📖 For full Git + SSH setup, see [Git & SSH Setup Guide](./docs/GIT_SSH_SETUP.md).

### Step 6: Clone & Run the Project

```bash
# Always clone inside WSL filesystem (much faster than /mnt/c/)
cd ~
git clone git@github.com:AparsoftAI/django-nextjs-chatbot.git
cd django-nextjs-chatbot
```

Then jump to [Quick Start](#2️⃣-quick-start-run-the-project) below.

---

## 🐧 Option B: Native Docker in WSL 2 (No Docker Desktop)

If you prefer running Docker natively inside WSL without Docker Desktop, follow these steps.

### Step 1: Install WSL 2 + Ubuntu

Open **PowerShell as Administrator**:

```powershell
wsl --install
```

Restart your computer, then launch Ubuntu from the Start Menu.

### Step 2: Update System Packages

```bash
sudo apt update
sudo apt upgrade -y
```

### Step 3: Install Prerequisites

```bash
sudo apt install -y ca-certificates curl gnupg lsb-release
```

### Step 4: Add Docker's Official GPG Key

```bash
sudo install -m 0755 -d /etc/apt/keyrings

curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

sudo chmod a+r /etc/apt/keyrings/docker.gpg
```

### Step 5: Set Up Docker Repository

```bash
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
```

### Step 6: Install Docker Engine

```bash
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

### Step 7: Start Docker Service

```bash
sudo service docker start
```

> ⚠️ **WSL quirk:** Docker won't auto-start when WSL restarts. See [Auto-start Docker in WSL](#auto-start-docker-in-wsl) below.

### Step 8: Add Your User to Docker Group

This lets you run Docker without `sudo`:

```bash
sudo usermod -aG docker $USER
newgrp docker
```

Log out and back in for this to take full effect.

### Step 9: Verify Installation

```bash
docker run hello-world
docker compose version
```

✅ You should see: `Hello from Docker!` and `Docker Compose version v2.x.x`.

### Step 10: Configure Git in WSL

```bash
sudo apt install git -y
git config --global user.name "Your Full Name"
git config --global user.email "you@example.com"
git config --global core.autocrlf input
```

> 📖 For full Git + SSH setup, see [Git & SSH Setup Guide](./docs/GIT_SSH_SETUP.md).

### Step 11: Clone & Run the Project

```bash
# Always clone inside WSL filesystem (much faster than /mnt/c/)
cd ~
git clone git@github.com:AparsoftAI/django-nextjs-chatbot.git
cd django-nextjs-chatbot
```

Then jump to [Quick Start](#2️⃣-quick-start-run-the-project) below.

---

## 🐧 Option C: Native Linux (Ubuntu/Debian)

If you're on a native Linux machine (no WSL):

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install prerequisites
sudo apt install -y ca-certificates curl gnupg lsb-release

# Add Docker GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add Docker repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Start and enable Docker on boot
sudo systemctl enable --now docker

# Verify
docker run hello-world
docker compose version
```

Then clone and proceed to [Quick Start](#2️⃣-quick-start-run-the-project).

---

## 🔧 WSL-Specific Configuration

### Auto-start Docker in WSL

Docker doesn't auto-start when WSL launches. Fix this by adding to your shell profile:

```bash
# Add to ~/.bashrc or ~/.zshrc
if ! service docker status > /dev/null 2>&1; then
    sudo service docker start > /dev/null 2>&1
fi
```

To allow `sudo service docker start` without a password prompt:

```bash
sudo visudo
# Add this line at the end (replace 'yourname' with your WSL username):
yourname ALL=(root) NOPASSWD: /usr/sbin/service docker start
```

### WSL Memory & Resource Limits

Create or edit `%USERPROFILE%\.wslconfig` on **Windows** (not in WSL):

```ini
[wsl2]
memory=8GB
processors=4
swap=2GB
localhostForwarding=true
```

Then restart WSL in PowerShell: `wsl --shutdown`

### WSL Filesystem Performance

```bash
# ✅ FAST — Work inside WSL's native filesystem
cd ~
git clone git@github.com:AparsoftAI/django-nextjs-chatbot.git

# ❌ SLOW — Avoid working on the Windows mount
# /mnt/c/Users/... is 3-5x slower for git operations
```

### Fix "Permission too open" for SSH Keys in WSL

```bash
chmod 700 ~/.ssh
chmod 600 ~/.ssh/id_ed25519
chmod 644 ~/.ssh/id_ed25519.pub
```

### Fix Port Forwarding (Windows ↔ WSL)

WSL 2 automatically forwards ports, but if you can't access `localhost:8000` from Windows:

```bash
# Check WSL IP
hostname -I | awk '{print $1}'
# e.g., 172.25.123.45

# From Windows PowerShell, add port proxy (run as admin):
netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 connectport=8000 connectaddress=172.25.123.45
```

To remove the proxy later:
```powershell
netsh interface portproxy delete v4tov4 listenport=8000 listenaddress=0.0.0.0
```

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
README.md
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
A: Edit `.wslconfig` in your Windows user folder (`%USERPROFILE%\.wslconfig`):
```ini
[wsl2]
memory=8GB
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

