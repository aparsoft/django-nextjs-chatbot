# 🤝 Contributing Guide — Aparsoft AI Chatbot

> This guide teaches you the **complete GitHub workflow** used in professional teams. Follow it every time you contribute code.

---

## Table of Contents

1. [One-Time Setup](#1-one-time-setup)
2. [The Contribution Workflow](#2-the-contribution-workflow)
3. [Branch Naming Rules](#3-branch-naming-rules)
4. [Writing Good Commits](#4-writing-good-commits)
5. [Creating a Pull Request](#5-creating-a-pull-request)
6. [Code Review Process](#6-code-review-process)
7. [Keeping Your Branch Updated](#7-keeping-your-branch-updated)
8. [Common Mistakes & How to Fix Them](#8-common-mistakes--how-to-fix-them)
9. [Code Style Rules](#9-code-style-rules)

---

## 1. One-Time Setup

Do these once when you first join:

### Configure Git identity
```bash
git config --global user.name "Your Full Name"
git config --global user.email "your.name@aparsoft.com"
```

### Set up SSH key (so you don't type passwords)
```bash
# Generate SSH key
ssh-keygen -t ed25519 -C "your.name@aparsoft.com"
# Press Enter for default location, set a passphrase

# Copy public key
cat ~/.ssh/id_ed25519.pub
# Add this to GitHub → Settings → SSH and GPG keys → New SSH key
```

### Fork the repository (if you don't have push access)
```bash
# 1. Click "Fork" on the GitHub repo page
# 2. Clone YOUR fork
git clone git@github.com:YOUR-USERNAME/django-nextjs-chatbot.git
cd django-nextjs-chatbot

# 3. Add the original repo as "upstream"
git remote add upstream git@github.com:aparsoft/django-nextjs-chatbot.git

# 4. Verify remotes
git remote -v
# origin    git@github.com:YOUR-USERNAME/django-nextjs-chatbot.git (fetch)
# origin    git@github.com:YOUR-USERNAME/django-nextjs-chatbot.git (push)
# upstream  git@github.com:aparsoft/django-nextjs-chatbot.git (fetch)
# upstream  git@github.com:aparsoft/django-nextjs-chatbot.git (push)
```

---

## 2. The Contribution Workflow

Follow this **every time** you work on a new feature or bugfix:

```
┌─────────────────────────────────────────────────────┐
│            THE CONTRIBUTION CYCLE                     │
│                                                      │
│  1. Sync main    →  git pull upstream main           │
│  2. Create branch →  git checkout -b feat/xxx        │
│  3. Write code   →  (edit files, test, repeat)       │
│  4. Commit       →  git add + git commit             │
│  5. Push         →  git push origin feat/xxx         │
│  6. Open PR      →  GitHub → New Pull Request        │
│  7. Get review   →  Address feedback, push fixes     │
│  8. Merge!       →  Maintainer merges to main        │
│  9. Clean up     →  Delete branch, sync main         │
└─────────────────────────────────────────────────────┘
```

### Step-by-step

```bash
# ① START: Always sync with latest main first
git checkout main
git pull upstream main        # If you forked
# OR
git pull origin main          # If you have direct push access

# ② CREATE: New branch for your work
git checkout -b feat/add-chat-session-api

# ③ CODE: Make your changes
# ... edit files ...
# ... test locally ...

# ④ COMMIT: Stage and commit (see "Writing Good Commits" below)
git add backend/apps/chatbot/api/views/chat_session_views.py
git commit -m "feat(chatbot): add ChatSession list and create endpoints"

# ⑤ PUSH: Push YOUR branch to YOUR fork
git push origin feat/add-chat-session-api

# ⑥ PR: Open a Pull Request on GitHub
# Go to github.com → your fork → "Compare & pull request"
# Fill in the PR template (see below)

# ⑦ REVIEW: A senior engineer reviews your code
# They may request changes — address them, push again

# ⑧ MERGE: After approval, maintainer merges

# ⑨ CLEANUP: Delete your feature branch
git checkout main
git pull upstream main
git branch -d feat/add-chat-session-api          # Delete local
git push origin --delete feat/add-chat-session-api  # Delete remote
```

---

## 3. Branch Naming Rules

Always prefix your branch with the type:

| Prefix | Use for | Example |
|--------|---------|---------|
| `feat/` | New feature | `feat/add-chat-session-api` |
| `fix/` | Bug fix | `fix/fix-session-archive-bug` |
| `docs/` | Documentation | `docs/add-onboarding-guide` |
| `refactor/` | Code cleanup (no new behavior) | `refactor/simplify-session-create` |
| `test/` | Adding tests | `test/add-session-model-tests` |
| `chore/` | Build, config, dependencies | `chore/update-django-version` |

**Rules:**
- Use kebab-case (lowercase with hyphens)
- Keep it short but descriptive
- Include the app/module name when relevant

```bash
# ✅ Good
git checkout -b feat/add-message-feedback-api
git checkout -b fix/fix-token-usage-calculation
git checkout -b docs/add-intern-onboarding

# ❌ Bad
git checkout -b my-branch
git checkout -b fix-bug
git checkout -b updates
```

---

## 4. Writing Good Commits

### The Conventional Commits Format

```
<type>(<scope>): <short description>

[optional body with more detail]

[optional footer with breaking changes or issue references]
```

### Types

| Type | Meaning | Example |
|------|---------|---------|
| `feat` | New feature | `feat(chatbot): add message feedback API` |
| `fix` | Bug fix | `fix(auth): handle expired JWT tokens correctly` |
| `docs` | Documentation | `docs(readme): update setup instructions` |
| `style` | Formatting (no logic change) | `style(chatbot): fix indentation in models` |
| `refactor` | Code restructure (no behavior change) | `refactor(tools): remove AvailableTool model` |
| `test` | Adding tests | `test(sessions): add tests for create_for_user` |
| `chore` | Build/config | `chore(docker): upgrade pgvector to pg17` |

### Rules

1. **Short description ≤ 72 characters** — GitHub truncates longer ones
2. **Use imperative mood** — "add feature" not "added feature"
3. **One logical change per commit** — don't mix unrelated changes
4. **Never commit secrets** — no API keys, passwords, or `.env` files

```bash
# ✅ Good commits
git commit -m "feat(chatbot): add ChatSession create_for_user class method"
git commit -m "fix(tokens): fix cost calculation for reasoning models"
git commit -m "docs(onboarding): add intern setup guide"

# ❌ Bad commits
git commit -m "fixed stuff"
git commit -m "WIP"
git commit -m "changes"
git commit -m "updated files"
```

### Multi-line commit (when you need a body)

```bash
git commit -m "feat(chatbot): add UserDocument processing state machine" -m "
Adds state transition methods to UserDocument model:
- mark_processing_started()
- mark_processing_completed()
- mark_processing_failed()
- can_retry_processing() with MAX_RETRIES=3
- retry_processing() resets status for retry

Also adds create_from_upload() factory method that
extracts metadata from Django UploadedFile automatically.
"
```

---

## 5. Creating a Pull Request

### PR Title Format

Same as commit format: `type(scope): description`

```
feat(chatbot): add ChatSession API endpoints
fix(tokens): correct cost calculation for o4 models
docs(onboarding): add intern contribution guide
```

### PR Description Template

```markdown
## What does this PR do?
<!-- Brief description of the change -->

Adds CRUD API endpoints for ChatSession model using the thin viewset pattern.

## Type of Change
- [ ] 🆕 New feature
- [ ] 🐛 Bug fix
- [ ] 📝 Documentation
- [ ] ♻️ Refactor
- [ ] ✅ Test

## How to Test
1. Start the dev server: `python manage.py runserver`
2. Login to admin: http://localhost:8000/chatbot-admin/
3. Go to http://localhost:8000/api/v1/sessions/
4. Try creating a session via POST

## Checklist
- [ ] Code follows project style (fatty models, thin viewsets)
- [ ] Added/updated model methods (no logic in viewsets)
- [ ] Added `to_display_dict()` method if model is new
- [ ] Migrations created: `python manage.py makemigrations`
- [ ] Tested locally
- [ ] No secrets committed

## Related Issues
<!-- Link any related issues: Closes #123 -->
```

### PR Size Guide

| Size | Lines Changed | Strategy |
|------|--------------|----------|
| 🟢 Small | < 100 | One feature, one PR |
| 🟡 Medium | 100-300 | OK if changes are related |
| 🔴 Large | > 300 | Split into smaller PRs! |

> 💡 **Smaller PRs get reviewed faster.** If your PR is huge, split it.

---

## 6. Code Review Process

### What to expect

1. You open a PR
2. A senior engineer is assigned as reviewer
3. They may:
   - ✅ Approve (ready to merge)
   - 💬 Comment (questions, suggestions)
   - ❌ Request changes (must fix before merge)
4. You address feedback by pushing new commits
5. Once approved, maintainer merges

### How to handle feedback

```bash
# Make changes locally
# ... edit files ...

# Commit the fix
git add .
git commit -m "fix(chatbot): address PR review feedback — use update_fields"

# Push to the same branch
git push origin feat/add-chat-session-api
# The PR auto-updates!
```

### Review your OWN code first

Before requesting review:
```bash
# Review your own diff
git diff main...HEAD

# Run tests
python manage.py test

# Check for debug prints, TODOs, secrets
grep -rn "print(" backend/apps/chatbot/
grep -rn "TODO" backend/apps/chatbot/
grep -rn "API_KEY" backend/apps/chatbot/
```

---

## 7. Keeping Your Branch Updated

When `main` gets updated while you're working:

```bash
# Save your work
git stash

# Update main
git checkout main
git pull upstream main

# Go back to your branch and rebase
git checkout feat/my-feature
git rebase main

# If there are conflicts:
# 1. Open conflicted files
# 2. Resolve conflicts (pick yours or theirs)
# 3. git add <resolved-files>
# 4. git rebase --continue

# Restore your stashed work
git stash pop
```

### Alternative: Merge (safer for beginners)

```bash
git checkout feat/my-feature
git fetch upstream
git merge upstream/main
# Resolve any conflicts, then commit
```

---

## 8. Common Mistakes & How to Fix Them

### ❌ Committed to main by accident
```bash
# Create a branch from current state
git checkout -b feat/my-actual-work

# Reset main back to upstream
git checkout main
git reset --hard upstream/main

# Go back to your branch and continue
git checkout feat/my-actual-work
```

### ❌ Committed wrong files
```bash
# Undo last commit but keep changes staged
git reset --soft HEAD~1

# Unstage the wrong file
git reset HEAD wrong_file.py

# Commit again with only the right files
git commit -m "feat(chatbot): the right commit"
```

### ❌ Pushed secrets to GitHub
```bash
# ⚠️ THIS IS SERIOUS — tell your mentor immediately!

# Remove the file from Git history
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch path/to/secret-file" \
  --prune-empty -- --all

# Force push (only safe if you're the only one on the branch)
git push origin --force --all

# Then ROTATE the compromised secret immediately!
```

### ❌ Merge conflicts during rebase
```bash
# See which files have conflicts
git status

# Open each conflicted file — look for <<<<<<< HEAD markers
# Choose the correct version (or combine both)
# Then:
git add <resolved-file>
git rebase --continue

# If you're completely lost:
git rebase --abort   # Cancel rebase, go back to before
```

### ❌ Branch is behind main and PR has conflicts
```bash
# On your feature branch:
git fetch upstream
git rebase upstream/main
git push origin feat/my-feature --force-with-lease
```

---

## 9. Code Style Rules

### Python (Backend)

1. **Fatty Models, Thin Viewsets** — business logic in model methods
2. **Every model gets `to_display_dict()`** — for API responses
3. **Use `update_fields`** in `save()` calls — `self.save(update_fields=["status"])`
4. **Type hints** on service methods — `def get_user_tools(user: CustomUser) -> List[UserTool]:`
5. **Docstrings** on all class methods — explain args, return type, and usage
6. **`@classmethod`** for queries — `get_active_for_user(user)` not `objects.filter(...)`
7. **No raw SQL** — use Django ORM always
8. **No `select_related` without reason** — but use it when you access FK fields

```python
# ✅ Good
class ChatSession(TimestampedModel):
    def archive(self):
        """Archive this session (inactive + archived)."""
        self.is_archived = True
        self.is_active = False
        self.save(update_fields=["is_archived", "is_active"])

# ❌ Bad
class ChatSession(TimestampedModel):
    def archive(self):
        self.is_archived = True
        self.is_active = False
        self.save()  # Missing update_fields — hits ALL columns
```

### Imports Order

```python
# 1. Standard library
import os
import uuid
from datetime import timedelta

# 2. Django
from django.db import models
from django.conf import settings
from django.utils import timezone

# 3. Third-party
from rest_framework import serializers
from decouple import config

# 4. Local
from core.models import TimestampedModel
from ..models import ChatSession
```

### File Organization

```
chatbot/
├── models/              ← Database models (FATTY)
│   ├── __init__.py
│   ├── chat_session.py
│   └── ...
├── services/            ← External integrations (LangGraph, APIs)
│   ├── chat_session_service.py
│   └── ...
├── api/
│   ├── serializers/     ← Data validation + JSON conversion
│   ├── views/           ← ViewSets (THIN)
│   └── urls.py          ← URL routing
├── management/
│   └── commands/        ← CLI scripts
└── migrations/          ← Auto-generated DB migration files
```

---

## Quick Reference Card

```
# Daily workflow
git checkout main && git pull upstream main
git checkout -b feat/my-feature
# ... code ...
git add -A && git commit -m "feat(scope): description"
git push origin feat/my-feature
# → Open PR on GitHub

# Emergency: undo last commit
git reset --soft HEAD~1

# Check what you've changed
git status                    # Modified files
git diff                      # Unstaged changes
git diff --staged             # Staged changes

# Check commit history
git log --oneline -10         # Last 10 commits
git log --oneline --graph     # Visual branch history
```

---

> 💬 **Questions?** Ask in the team Slack. We're here to help you succeed!
