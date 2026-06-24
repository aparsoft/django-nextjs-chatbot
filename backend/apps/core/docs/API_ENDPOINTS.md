# Core API Endpoints

> Base: `/api/v1/` · Auth: `Authorization: Bearer <access>`

---

## Status

The `core` app is a **shared utility app** — it provides base models, permissions, and
helpers used by `accounts` and `chatbot`. It has **no dedicated API endpoints** of its own.

### What core provides (not API endpoints)

| Component | Location | Purpose |
|-----------|----------|---------|
| `TimestampedModel` | `core/models/` | Abstract base with `created_at` / `updated_at` |
| `Country` | `core/models/` | Geography model (referenced by `UserContact.country`) |
| `IsOwnerOrAdmin` | `core/permissions/` | Object-level permission — owner or admin only |
| `IsOwner` | `core/permissions/` | Object-level permission — owner only |
| `IsAdminOrReadOnly` | `core/permissions/` | Admin can write, others read-only |
| `IsAdminUser` | `core/permissions/` | Admin role required |

### Endpoints that reference core models

Core's `Country` model is exposed indirectly through the accounts app:

- `GET /api/v1/accounts/user-contacts/` → `country` field (FK to `Country`), `country_name` (read-only string)
- `POST /api/v1/accounts/user-contacts/` → `country` field accepts a `Country` PK (integer)

No direct `/api/v1/core/` endpoints exist.