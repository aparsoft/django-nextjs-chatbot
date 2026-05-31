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
| `lib/api.js` | Server-side fetch (reads cookies, injects Bearer header) |
| `lib/api-client.js` | Client-side fetch (calls /api/proxy/...) |
| `lib/cookies.js` | Cookie constants: names, max-ages, options |
| `lib/ws.js` | WebSocket connection manager (auth frame pattern) |

---

## `hooks/` — ❌ Does Not Exist

| Hook | Purpose |
|------|---------|
| `hooks/useChat.js` | Chat state management, message sending, streaming |
| `hooks/useWebSocket.js` | WebSocket lifecycle (connect, disconnect, auth frame) |

---

## Auth (BFF Proxy Pattern) — ❌ Not Implemented

| Component | Status | Details |
|-----------|--------|---------|
| `middleware.js` | ❌ | Route protection (cookie existence check) |
| `app/api/auth/login/route.js` | ❌ | Login proxy → Django |
| `app/api/auth/refresh/route.js` | ❌ | Refresh proxy with concurrency lock |
| `app/api/auth/logout/route.js` | ❌ | Logout + Django blacklist |
| `app/api/proxy/[...path]/route.js` | ❌ | Generic API proxy (injects Bearer header) |
| `lib/cookies.js` | ❌ | Cookie constants |
| `.env.local` | ⚠️ Partial | Has stale `AUTH_SECRET` (not needed); missing `INTERNAL_API_URL` |
| Auth playbook | ✅ Documented | Full plan in `docs/AUTHENTICATION_PLAYBOOK.md` |

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

### Phase 1 — Auth Foundation (BFF Proxy)
1. **`lib/cookies.js`** — Cookie constants (names, max-ages, options)
2. **`app/api/auth/login/route.js`** — Login proxy → Django, sets httpOnly cookies
3. **`app/api/auth/refresh/route.js`** — Refresh proxy with concurrency lock
4. **`app/api/auth/logout/route.js`** — Logout + Django blacklist + clear cookies
5. **`app/api/auth/me/route.js`** — Current user proxy
6. **`middleware.js`** — Route protection (cookie existence check)
7. **`app/login/page.jsx`** — Login form (calls /api/auth/login)
8. **Update `.env.example`** — Remove `AUTH_SECRET`, add `INTERNAL_API_URL`

### Phase 2 — Layout & Navigation
9. **`app/(app)/layout.jsx`** — Authenticated layout with server-side token validation
10. **`app/api/proxy/[...path]/route.js`** — Generic API proxy (injects Bearer header)
11. **`components/layout/`** — Sidebar navigation, header with user menu
12. **`app/page.js`** — Replace scaffold with redirect to `/chat` or landing page

### Phase 3 — Core Features
13. **`lib/api.js`** — Server-side fetch helper (reads cookies, injects Bearer)
14. **`lib/api-client.js`** — Client-side fetch helper (calls /api/proxy/...)
15. **`app/(app)/chat/page.jsx`** — Chat interface (session list + message area + input)
16. **`components/chat/`** — Message bubble, input bar, session list
17. **`hooks/useChat.js`** — Chat state management hook

### Phase 4 — Supporting Features
18. **`app/(app)/documents/page.jsx`** — Document upload and management
19. **`app/(app)/settings/page.jsx`** — User preferences (model, temperature)
20. **`app/(app)/analytics/page.jsx`** — Token usage dashboard

### Phase 5 — Real-Time & Testing
21. **`lib/ws.js`** + **`hooks/useWebSocket.js`** — WebSocket streaming (auth frame pattern)
22. **`vitest.config.mjs`** + **`__tests__/setup.js`** — Test infrastructure
23. **Tests** — Auth routes, middleware, proxy, chat components

---

## Build & Lint Status

| Check | Status |
|-------|--------|
| `npm run build` | ✅ Passes (0 errors, 0 warnings) |
| `npm run lint` | ✅ Passes clean |
| `npm run test` | ⚠️ Exits "no test files found" (expected — no tests yet) |
