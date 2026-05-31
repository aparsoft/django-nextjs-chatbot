# Vision — Django + Next.js AI Chatbot (Frontend)

> What we're building and why. The north star for every frontend design decision.

---

## The Mission

Build a **modern chat interface** that connects to the Django backend and gives users a clean, fast, and intuitive way to interact with AI. Every component should be simple enough for an intern to understand, accessible enough for a YouTube tutorial, and polished enough to feel like a real product.

**We are building in public** — this is the [Aparsoft YouTube tutorial series](https://youtube.com/@aparsoft). The codebase IS the curriculum.

---

## Product Vision

The platform is a **Customer Conversational AI Chatbot** — the frontend delivers:

1. **Chat Interface** — Real-time messaging with streaming AI responses
2. **Document Management** — Upload files, track processing status, browse indexed content
3. **Settings Dashboard** — Model selection, temperature, tool toggles, API key management
4. **Analytics** — Token usage charts, cost breakdown, feedback summaries
5. **Auth Flow** — Secure login/register with server-side sessions (no localStorage JWT)

---

## Architecture Principles

### Server Components First

Next.js App Router defaults to Server Components. Use them for data fetching, auth checks, and static content. Only add `"use client"` when you need interactivity (hooks, browser APIs, event handlers).

```
Server Component (default)     Client Component ("use client")
├── Auth checks                ├── useState, useEffect
├── Data fetching              ├── Event handlers (onClick, onSubmit)
├── SEO metadata               ├── Browser APIs (WebSocket, localStorage)
├── Static rendering           ├── Interactive UI (forms, modals, chat input)
```

### Thin Components, Smart Hooks

Business logic lives in hooks and lib functions, not in components. Components render UI.

```
Component → Hook → lib/api.js → Backend
  (UI)      (state)   (fetch)
```

### Route Groups for Layout Strategy

```
app/
├── (app)/          ← Authenticated pages (sidebar, header, protected)
├── login/          ← Unauthenticated (minimal layout)
└── api/auth/       ← Auth.js handlers
```

### CSS-First with Tailwind v4

No UI component library (Material UI, Chakra, etc.). Tailwind CSS v4 gives us everything:
- CSS-first configuration (no `tailwind.config.js`)
- Built-in dark mode
- Zero runtime overhead
- Easy to understand for beginners

### Co-Located Tests

Tests live in `__tests__/` at the frontend root. Each test file mirrors the source path:

```
components/chat/message-bubble.jsx  →  __tests__/components/chat/message-bubble.test.jsx
hooks/useChat.js                    →  __tests__/hooks/useChat.test.js
```

---

## Technology Decisions

| Choice | Why |
|--------|-----|
| **Next.js 16 (App Router)** | Latest features, server components, Turbopack for fast builds. App Router is the standard going forward. |
| **React 19** | Server components, improvedSuspense, use() hook. Latest stable. |
| **Tailwind CSS v4** | CSS-first config, no build step for config, zero runtime. Simpler than v3 for newcomers. |
| **NextAuth.js v5 (Auth.js)** | Server-side sessions with httpOnly cookies — eliminates XSS risk from localStorage JWT. Direct integration with Django backend. |
| **Vitest + Testing Library** | Fast, ESM-native test runner. Testing Library tests user behavior, not implementation details. |
| **JavaScript (no TypeScript)** | Lower barrier for interns. jsconfig with path aliases gives IDE support without TS complexity. Can migrate later if needed. |
| **Turbopack** | Next.js 16's default bundler. Significantly faster than Webpack for dev. |

---

## Target Architecture (End State)

```
┌─────────────────────────────────────────────────────────────┐
│                      Browser                                │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  Server       │  │  Client       │  │  WebSocket       │  │
│  │  Components   │  │  Components   │  │  (streaming)     │  │
│  │  (data fetch, │  │  (interactive │  │                  │  │
│  │   auth, SEO)  │  │   UI, hooks)  │  │                  │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
│         │                 │                     │            │
│  ┌──────▼─────────────────▼─────────────────────▼─────────┐ │
│  │                     lib/                                │ │
│  │  api.js          auth-client.js        ws.js           │ │
│  │  (REST calls)    (session helpers)     (WebSocket)     │ │
│  └──────────┬──────────────────┬─────────────────┬────────┘ │
└─────────────┼──────────────────┼─────────────────┼──────────┘
              │                  │                 │
              ▼                  ▼                 ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  Django Backend  │  │  Auth.js         │  │  Django          │
│  /api/v1/*       │  │  Session Cookie  │  │  WebSocket       │
│  (REST API)      │  │  (httpOnly)      │  │  /ws/chat/*      │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

---

## Page Inventory

| Route | Page | Type | Key Features |
|-------|------|------|-------------|
| `/login` | Login | Unauthenticated | Email/password form, register link, error handling |
| `/chat` | Chat Home | Authenticated | Session list sidebar, new chat button |
| `/chat/[id]` | Chat Session | Authenticated | Message thread, streaming input, feedback buttons |
| `/documents` | Documents | Authenticated | Upload dropzone, file list, processing status |
| `/settings` | Settings | Authenticated | Model, temperature, tools, API keys |
| `/analytics` | Analytics | Authenticated | Token usage charts, cost breakdown |

---

## Component Hierarchy

```
app/layout.js                          ← Fonts, metadata, globals
├── app/login/page.jsx                 ← Login form
└── app/(app)/layout.jsx               ← Protected layout
    ├── components/layout/sidebar.jsx  ← Navigation
    ├── components/layout/header.jsx   ← User menu, breadcrumbs
    └── <children>                     ← Page content
        ├── app/(app)/chat/page.jsx
        │   ├── components/chat/session-list.jsx
        │   └── components/chat/message-area.jsx
        │       ├── components/chat/message-bubble.jsx
        │       ├── components/chat/streaming-indicator.jsx
        │       └── components/chat/message-input.jsx
        ├── app/(app)/documents/page.jsx
        │   ├── components/documents/upload-dropzone.jsx
        │   └── components/documents/file-list.jsx
        ├── app/(app)/settings/page.jsx
        └── app/(app)/analytics/page.jsx
```

---

## What "Done" Looks Like

- [ ] Auth flow: login → session cookie → protected routes → logout
- [ ] Chat UI: session list, message thread, streaming input, feedback buttons
- [ ] Document upload: drag-and-drop, processing status, file list
- [ ] Settings page: model selector, temperature slider, tool toggles
- [ ] Analytics page: token usage, cost charts
- [ ] Responsive layout: desktop sidebar, mobile hamburger menu
- [ ] Dark mode: system preference + manual toggle
- [ ] Vitest config + 20+ tests (auth, components, hooks)
- [ ] Production Dockerfile (multi-stage build)
- [ ] Updated `.env.example` with all variables

---

## What This Is NOT

- Not a design system or component library
- Not a mobile app (React Native is separate for AparAcademy)
- Not using TypeScript (JavaScript only, may migrate later)
- Not using a UI framework (MUI, Chakra, etc.) — Tailwind only
- Not over-engineered — every component exists because it teaches something

---

## Audience

1. **Interns** joining Aparsoft — they should be productive in a week
2. **YouTube viewers** — they follow along at home, so code must be readable
3. **Future us** — six months from now we need to remember why we made each choice

If a design decision doesn't serve one of these audiences, reconsider it.
