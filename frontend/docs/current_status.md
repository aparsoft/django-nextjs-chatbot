# Current Status — Django + Next.js AI Chatbot (Frontend)

> Snapshot of what's built, what's wired, and what's still a stub. Updated May 2026.

---

## Infrastructure ✅

| Component | Status | Details |
|-----------|--------|---------|
| Next.js 16 (App Router) | ✅ Running | Turbopack enabled for dev + build |
| React 19 | ✅ Installed | 19.2.6 |
| Tailwind CSS v4 | ✅ Configured | CSS-first via `@tailwindcss/postcss`, no `tailwind.config.js` |
| ESLint (flat config) | ✅ Working | `eslint-config-next` native flat config |
| Vitest | ✅ Installed | 4.1.7 + Testing Library + jsdom, no config file yet |
| Path aliases | ✅ Working | `@/*` → `./*` via `jsconfig.json` |
| Dockerfile | ⚠️ Dev only | Single-stage, runs `npm run dev` — not production-ready |
| Environment variables | ⚠️ Partial | `.env.local` has 6 vars, `.env.example` only has 2 (out of date) |

---

## `app/` — ⚠️ Scaffold Only

| File | Status | Details |
|------|--------|---------|
| `layout.js` | ✅ | Root layout with Geist fonts, metadata, globals |
| `page.js` | ⚠️ Scaffold | Still the default `create-next-app` boilerplate |
| `globals.css` | ✅ | Tailwind v4 import + theme variables + dark mode |
| `favicon.ico` | ✅ | Default Next.js favicon |
| `login/page.jsx` | ❌ | Login page |
| `(app)/layout.jsx` | ❌ | Authenticated layout (session check, sidebar) |
| `(app)/chat/page.jsx` | ❌ | Chat interface |
| `(app)/documents/page.jsx` | ❌ | Document management |
| `(app)/settings/page.jsx` | ❌ | User preferences |
| `(app)/analytics/page.jsx` | ❌ | Token usage & costs |
| `api/auth/[...nextauth]/route.js` | ❌ | Auth.js catch-all handler |

---

## `components/` — ❌ Does Not Exist

| Directory | Planned Contents |
|-----------|-----------------|
| `components/ui/` | Buttons, inputs, cards, modals, toasts |
| `components/chat/` | Message bubble, input bar, session list, streaming indicator |
| `components/layout/` | Sidebar, header, navigation, user menu |
| `components/documents/` | Upload dropzone, file list, status badges |

---

## `lib/` — ❌ Does Not Exist

| File | Purpose |
|------|---------|
| `lib/api.js` | Fetch wrapper with JWT auth, refresh, error handling |
| `lib/auth-client.js` | Client-side auth helpers (signIn, signOut, useSession) |
| `lib/ws.js` | WebSocket connection manager for streaming |

---

## `hooks/` — ❌ Does Not Exist

| Hook | Purpose |
|------|---------|
| `hooks/useChat.js` | Chat state management, message sending, streaming |
| `hooks/useAuth.js` | Session access shortcut for client components |
| `hooks/useWebSocket.js` | WebSocket lifecycle (connect, disconnect, reconnect) |

---

## Auth (NextAuth.js v5) — ❌ Not Implemented

| Component | Status | Details |
|-----------|--------|---------|
| `next-auth` package | ✅ Installed | 5.0.0-beta.31 |
| `auth.js` config | ❌ | Not created — Credentials provider + Django backend adapter |
| `middleware.js` | ❌ | Route protection not implemented |
| `app/api/auth/[...nextauth]/route.js` | ❌ | Route handler not created |
| `.env.local` auth vars | ⚠️ Partial | Placeholders exist (`AUTH_SECRET` still dummy value) |
| Auth integration plan | ✅ Documented | Full playbook in `docs/AUTHJS_INTEGRATION.md` |

---

## Testing — ❌ Not Started

| Component | Status | Details |
|-----------|--------|---------|
| Vitest | ✅ Installed | 4.1.7 in devDependencies |
| Testing Library | ✅ Installed | React, DOM, jest-dom, user-event |
| jsdom | ✅ Installed | Browser environment for tests |
| `vitest.config.mjs` | ❌ | No config file — needs `@vitejs/plugin-react` setup |
| `__tests__/setup.js` | ❌ | No test setup file |
| Test files | ❌ | No tests written |
| Test scripts | ✅ | `test`, `test:watch`, `test:coverage` in package.json |

---

## Static Assets — ✅ Scaffold

| File | Details |
|------|---------|
| `public/file.svg` | Default Next.js icon |
| `public/globe.svg` | Default Next.js icon |
| `public/next.svg` | Next.js logo |
| `public/vercel.svg` | Vercel logo |
| `public/window.svg` | Default Next.js icon |

> These are all default scaffold assets — replace with project branding when ready.

---

## Configuration Files — ✅

| File | Status | Details |
|------|--------|---------|
| `next.config.mjs` | ✅ | Empty config (no rewrites, redirects, or images config) |
| `postcss.config.mjs` | ✅ | `@tailwindcss/postcss` plugin |
| `eslint.config.mjs` | ✅ | Flat config with `eslint-config-next`, ignore patterns |
| `jsconfig.json` | ✅ | `@/*` path alias |
| `package.json` | ✅ | Updated with latest packages |
| `.env.example` | ⚠️ | Out of date — missing auth vars, WS host, base URL |
| `.gitignore` | ✅ | Standard Next.js gitignore |

---

## Priority Checklist (What to Build Next)

### Phase 1 — Auth Foundation
1. **`auth.js`** — Configure Auth.js with Credentials provider pointing to Django backend
2. **`middleware.js`** — Route protection (redirect unauthenticated to `/login`)
3. **`app/api/auth/[...nextauth]/route.js`** — Wire up the auth route handler
4. **`app/login/page.jsx`** — Login form with email/password
5. **Update `.env.example`** — Sync with `.env.local` variables

### Phase 2 — Layout & Navigation
6. **`app/(app)/layout.jsx`** — Authenticated layout with sidebar, header, session check
7. **`components/layout/`** — Sidebar navigation, header with user menu
8. **`app/page.js`** — Replace scaffold with redirect to `/chat` or landing page

### Phase 3 — Core Features
9. **`lib/api.js`** — API client with JWT auth and error handling
10. **`app/(app)/chat/page.jsx`** — Chat interface (session list + message area + input)
11. **`components/chat/`** — Message bubble, input bar, session list
12. **`hooks/useChat.js`** — Chat state management hook

### Phase 4 — Supporting Features
13. **`app/(app)/documents/page.jsx`** — Document upload and management
14. **`app/(app)/settings/page.jsx`** — User preferences (model, temperature)
15. **`app/(app)/analytics/page.jsx`** — Token usage dashboard

### Phase 5 — Real-Time & Testing
16. **`lib/ws.js`** + **`hooks/useWebSocket.js`** — WebSocket streaming for chat
17. **`vitest.config.mjs`** + **`__tests__/setup.js`** — Test infrastructure
18. **Tests** — Auth, middleware, chat components, API layer

---

## Build & Lint Status

| Check | Status |
|-------|--------|
| `npm run build` | ✅ Passes (0 errors, 0 warnings) |
| `npm run lint` | ✅ Passes clean |
| `npm run test` | ⚠️ Exits "no test files found" (expected — no tests yet) |
