# 🔐 Git & SSH Setup Guide — Windows & WSL/Linux

> **This guide walks you through installing Git, configuring it, generating SSH keys, and connecting to GitHub** — whether you're on native Windows, WSL (Windows Subsystem for Linux), or a native Linux machine.

---

## 📋 Table of Contents

1. [Install Git](#1-install-git)
2. [Configure Git](#2-configure-git)
3. [Generate an SSH Key](#3-generate-an-ssh-key)
4. [Add the SSH Key to GitHub](#4-add-the-ssh-key-to-github)
5. [Test the SSH Connection](#5-test-the-ssh-connection)
6. [Clone the Repo with SSH](#6-clone-the-repo-with-ssh)
7. [Git Basics — Daily Workflow](#7-git-basics--daily-workflow)
8. [WSL-Specific Tips](#8-wsl-specific-tips)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Install Git

### 🪟 Windows

1. Download the installer from [git-scm.com](https://git-scm.com/download/win)
2. Run the `.exe` installer. **Important settings during installation:**
   - **Default editor:** Choose VS Code (or your preferred editor)
   - **PATH environment:** Select **"Git from the command line and also from 3rd-party software"**
   - **SSH executable:** Select **"Use bundled OpenSSH"**
   - **HTTPS transport backend:** Select **"Use the native Windows Secure Channel library"**
   - **Line ending conversions:** Select **"Checkout Windows-style, commit Unix-style"** (default)
3. After installation, open **Git Bash** (search in Start Menu) and verify:

```bash
git --version
# Expected: git version 2.4x.x
```

### 🐧 WSL / Linux (Debian/Ubuntu)

```bash
# Update package lists
sudo apt update && sudo apt upgrade -y

# Install Git
sudo apt install git -y

# Verify
git --version
# Expected: git version 2.4x.x
```

> 💡 **WSL users:** Run these commands *inside* your WSL terminal, not in Windows CMD/PowerShell.

---

## 2. Configure Git

These settings tell Git who you are and how you want it to behave. Run these **on every machine** (Windows Git Bash AND WSL/Linux).

```bash
# Your name (shows up in commit history)
git config --global user.name "Your Full Name"

# Your email (must match your GitHub email)
git config --global user.email "you@example.com"

# Default branch name (modern convention)
git config --global init.defaultBranch main

# Line ending settings (prevents CRLF/LF issues)
# On Windows (Git Bash):
git config --global core.autocrlf true
# On WSL/Linux:
git config --global core.autocrlf input

# Use VS Code as default editor for commit messages
git config --global core.editor "code --wait"

# Cache HTTPS credentials (optional, useful if you also use HTTPS)
git config --global credential.helper cache --timeout=3600

# Better default behavior
git config --global pull.rebase false
git config --global fetch.prune true
```

### Verify your settings

```bash
git config --global --list
```

You should see:
```
user.name=Your Full Name
user.email=you@example.com
init.defaultbranch=main
core.autocrlf=true          # (Windows) or input (WSL/Linux)
core.editor=code --wait
```

> ⚠️ **Important:** Use the **same name and email** on both Windows and WSL so your commits have a consistent identity.

---

## 3. Generate an SSH Key

SSH keys let you authenticate with GitHub without typing your password every time. Think of it as a digital ID card — you keep the private key, GitHub gets the public key.

### 🪟 Windows (Git Bash)

```bash
# Open Git Bash (not CMD or PowerShell)

# Generate a new Ed25519 key (modern, secure, fast)
ssh-keygen -t ed25519 -C "you@example.com"

# When prompted:
#   File to save:  Press Enter (accepts default: ~/.ssh/id_ed25519)
#   Passphrase:    Type a strong passphrase (or press Enter for none)
#   Confirm:       Re-type the passphrase

# Start the SSH agent
eval "$(ssh-agent -s)"

# Add your key to the agent
ssh-add ~/.ssh/id_ed25519
```

### 🐧 WSL / Linux

```bash
# Generate a new Ed25519 key
ssh-keygen -t ed25519 -C "you@example.com"

# When prompted:
#   File to save:  Press Enter (accepts default: ~/.ssh/id_ed25519)
#   Passphrase:    Type a strong passphrase (or press Enter for none)
#   Confirm:       Re-type the passphrase

# Start the SSH agent
eval "$(ssh-agent -s)"

# Add your key to the agent
ssh-add ~/.ssh/id_ed25519
```

### 🔑 About the Key Files

After generation, you'll have two files:

| File | Location | Purpose | Share? |
|------|----------|---------|--------|
| `id_ed25519` | `~/.ssh/id_ed25519` | **Private key** — your secret identity | ❌ **NEVER** |
| `id_ed25519.pub` | `~/.ssh/id_ed25519.pub` | **Public key** — goes on GitHub | ✅ Yes |

> 🚨 **CRITICAL:** Never share your private key (`id_ed25519`) with anyone. Never commit it to Git. Never paste it in Slack. Treat it like your password.

### View your public key

You'll need this in the next step:

```bash
cat ~/.ssh/id_ed25519.pub
```

Copy the entire output — it looks like:
```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI... you@example.com
```

---

## 4. Add the SSH Key to GitHub

1. Go to [github.com](https://github.com) and sign in
2. Click your **avatar** (top-right) → **Settings**
3. In the left sidebar, click **SSH and GPG keys**
4. Click **New SSH key**
5. Fill in:
   - **Title:** Something descriptive, e.g., `Windows Laptop` or `WSL Ubuntu`
   - **Key type:** Authentication Key
   - **Key:** Paste the entire output from `cat ~/.ssh/id_ed25519.pub`
6. Click **Add SSH key**
7. Confirm with your GitHub password if prompted

> 💡 **Tip:** If you use both Windows and WSL, you can add **two** keys — one from each environment. Give them descriptive titles so you know which is which.

---

## 5. Test the SSH Connection

```bash
ssh -T git@github.com
```

You should see:
```
Hi <username>! You've successfully authenticated, but GitHub does not provide shell access.
```

If it's your first time connecting, you'll see:
```
The authenticity of host 'github.com' (140.82.121.3)' can't be established.
ED25519 key fingerprint is SHA256:...
Are you sure you want to continue connecting (yes/no/[fingerprint])?
```

**Type `yes` and press Enter.** This adds GitHub to your known hosts.

---

## 6. Clone the Repo with SSH

Now you can clone using the SSH URL instead of HTTPS:

```bash
# Clone the repository
git clone git@github.com:AparsoftAI/django-nextjs-chatbot.git

# Enter the project directory
cd django-nextjs-chatbot
```

### Already cloned with HTTPS? Switch to SSH

```bash
cd django-nextjs-chatbot

# Check current remote
git remote -v
# origin  https://github.com/AparsoftAI/django-nextjs-chatbot.git (fetch)
# origin  https://github.com/AparsoftAI/django-nextjs-chatbot.git (push)

# Switch to SSH
git remote set-url origin git@github.com:AparsoftAI/django-nextjs-chatbot.git

# Verify
git remote -v
# origin  git@github.com:AparsoftAI/django-nextjs-chatbot.git (fetch)
# origin  git@github.com:AparsoftAI/django-nextjs-chatbot.git (push)
```

---

## 7. Git Basics — Daily Workflow

### The everyday cycle

```
  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
  │  git pull │───▶│  Make    │───▶│  git add │───▶│ git      │───▶│  git     │
  │  (sync)   │    │  changes │    │          │    │ commit   │    │  push    │
  └──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
```

### Before you start working (every time!)

```bash
# Switch to main and get the latest
git checkout main
git pull origin main

# Create a feature branch for your task
git checkout -b feature/your-task-name
# Examples:
#   git checkout -b feature/add-seed-command
#   git checkout -b fix/session-creation-bug
#   git checkout -b docs/update-readme
```

### While working

```bash
# Check what you've changed
git status

# See the actual diff
git diff

# Stage specific files
git add path/to/file.py

# Or stage everything (be careful!)
git add .

# Commit with a descriptive message
git commit -m "Add seed_demo management command"

# Push your branch to GitHub
git push origin feature/your-task-name
```

### Commit message conventions

```
type(scope): description

# Types:
#   feat:     New feature
#   fix:      Bug fix
#   docs:     Documentation
#   refactor: Code restructure (no behavior change)
#   test:     Adding tests
#   chore:    Maintenance (deps, configs)

# Examples:
feat(chatbot): add seed_demo management command
fix(accounts): resolve login redirect loop
docs(onboarding): add Git & SSH setup guide
refactor(chatbot): extract session creation to model method
test(chatbot): add tests for ChatSession.create_for_user
```

### Create a Pull Request

1. Push your branch to GitHub: `git push origin feature/your-task-name`
2. Go to the repo on GitHub
3. Click **"Compare & pull request"**
4. Fill in the PR template
5. Request a review from your mentor

### Keep your branch up to date

```bash
# While working on your feature branch, main may have moved forward.
# Rebase your branch on top of the latest main:

git checkout main
git pull origin main
git checkout feature/your-task-name
git rebase main

# If there are conflicts, resolve them, then:
git add .
git rebase --continue

# Force push after rebase (only your own branch!)
git push origin feature/your-task-name --force-with-lease
```

---

## 8. WSL-Specific Tips

### Sharing SSH keys between Windows and WSL

By default, Windows and WSL have **separate** SSH key directories:

| Environment | SSH Key Location |
|-------------|-----------------|
| Windows (Git Bash) | `C:\Users\YourName\.ssh\` |
| WSL | `/home/yourname/.ssh/` |

You have **two options**:

#### Option A: Generate separate keys (Recommended)

Generate one key in Git Bash and another in WSL. Add both to GitHub with descriptive titles:

```
Title: "Windows Laptop"     → Windows key
Title: "WSL Ubuntu 24.04"  → WSL key
```

#### Option B: Share the Windows key with WSL

```bash
# Inside WSL, create a symlink to the Windows SSH directory
ln -s /mnt/c/Users/YourName/.ssh ~/.ssh

# Fix permissions (WSL often gets Windows file permissions wrong)
chmod 700 ~/.ssh
chmod 600 ~/.ssh/id_ed25519
chmod 644 ~/.ssh/id_ed25519.pub
```

> ⚠️ **Warning:** Option B can cause permission headaches. Option A is more reliable.

### WSL SSH agent auto-start

Add this to your `~/.bashrc` (or `~/.zshrc`) so the SSH agent starts automatically:

```bash
# Auto-start SSH agent
if [ -z "$SSH_AUTH_SOCK" ]; then
   eval "$(ssh-agent -s)"
   ssh-add ~/.ssh/id_ed25519 2>/dev/null
fi
```

### Accessing Windows files from WSL

```bash
# Windows C: drive is mounted at /mnt/c/
ls /mnt/c/Users/YourName/Desktop

# Your project can live in either place, but WSL filesystem is faster
# Recommended: Clone repos inside WSL
cd ~
git clone git@github.com:AparsoftAI/django-nextjs-chatbot.git
```

> 💡 **Performance tip:** Git operations are **significantly faster** when the repo is on the WSL filesystem (`/home/...`) rather than the Windows filesystem (`/mnt/c/...`). Always clone and work inside WSL's native filesystem.

### Fix "Permission too open" error in WSL

```bash
# SSH requires strict permissions. If you see:
#   "Permissions 0644 for '/home/you/.ssh/id_ed25519' are too open"

chmod 700 ~/.ssh
chmod 600 ~/.ssh/id_ed25519
chmod 644 ~/.ssh/id_ed25519.pub
chmod 644 ~/.ssh/known_hosts
```

---

## 9. Troubleshooting

### "Permission denied (publickey)"

```bash
# 1. Check if SSH key is loaded
ssh-add -l
# Should show your key. If not:
ssh-add ~/.ssh/id_ed25519

# 2. Verify the key matches what's on GitHub
ssh -T git@github.com

# 3. Check you're using the SSH URL, not HTTPS
git remote -v
# Should show: git@github.com:AparsoftAI/...
# NOT: https://github.com/AparsoftAI/...
```

### "Host key verification failed"

```bash
# Add GitHub to known hosts
ssh-keyscan github.com >> ~/.ssh/known_hosts
```

### "fatal: remote origin already exists"

```bash
# You ran git remote add twice. Fix it:
git remote set-url origin git@github.com:AparsoftAI/django-nextjs-chatbot.git
```

### "SSL certificate problem" (Windows)

```bash
# Temporarily disable SSL check (NOT recommended for production)
git config --global http.sslVerify false

# Better: Update Git for Windows to the latest version
# Or: Set the CA bundle
git config --global http.sslCAInfo "C:/Program Files/Git/mingw64/ssl/certs/ca-bundle.crt"
```

### "LF will be replaced by CRLF" warnings

```bash
# On Windows, this is normal. To suppress the warning:
git config --global core.autocrlf true

# Create a .gitattributes file in the repo root (project-wide fix):
echo "* text=auto eol=lf" > .gitattributes
```

### Git asks for password every time (HTTPS)

```bash
# Switch to SSH (recommended):
git remote set-url origin git@github.com:AparsoftAI/django-nextjs-chatbot.git

# Or use the credential helper (Windows):
git config --global credential.helper manager

# Or cache credentials temporarily (Linux/WSL):
git config --global credential.helper cache --timeout=3600
```

### WSL: "git is not installed"

```bash
# Install Git inside WSL
sudo apt update && sudo apt install git -y
```

### WSL: Git operations are very slow

```bash
# Check if your repo is on the Windows filesystem
pwd
# If it starts with /mnt/c/... it's on Windows — move it to WSL:
# 1. Clone fresh inside WSL
cd ~
git clone git@github.com:AparsoftAI/django-nextjs-chatbot.git

# 2. Or move the repo
mv /mnt/c/Users/You/projects/django-nextjs-chatbot ~/projects/
cd ~/projects/django-nextjs-chatbot
```

### Reset everything and start fresh

```bash
# ⚠️ This deletes your SSH keys! Only use as last resort.

# Remove old keys
rm -f ~/.ssh/id_ed25519 ~/.ssh/id_ed25519.pub

# Generate new key
ssh-keygen -t ed25519 -C "you@example.com"

# Add to agent
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519

# Copy public key
cat ~/.ssh/id_ed25519.pub
# → Paste into GitHub Settings → SSH Keys → New SSH key

# Test
ssh -T git@github.com
```

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│                    GIT & SSH CHEAT SHEET                     │
├─────────────────────────────────────────────────────────────┤
│ SETUP (one-time)                                            │
│   git config --global user.name "Name"                      │
│   git config --global user.email "you@example.com"         │
│   ssh-keygen -t ed25519 -C "you@example.com"               │
│   ssh-add ~/.ssh/id_ed25519                                 │
│   → Add public key to GitHub                                │
│                                                             │
│ DAILY WORKFLOW                                              │
│   git pull origin main                                      │
│   git checkout -b feature/task-name                         │
│   git add .                                                 │
│   git commit -m "type(scope): description"                  │
│   git push origin feature/task-name                         │
│   → Open Pull Request on GitHub                             │
│                                                             │
│ SYNC BRANCH                                                 │
│   git checkout main && git pull origin main                  │
│   git checkout feature/task-name                            │
│   git rebase main                                           │
│                                                             │
│ TROUBLESHOOT                                                │
│   ssh -T git@github.com          # Test connection          │
│   ssh-add -l                     # List loaded keys         │
│   git remote -v                  # Check remote URL         │
│   chmod 600 ~/.ssh/id_ed25519   # Fix WSL permissions      │
└─────────────────────────────────────────────────────────────┘
```

---

> 💬 **Stuck?** Ask in the team Slack channel. No question is too basic — we all started somewhere!