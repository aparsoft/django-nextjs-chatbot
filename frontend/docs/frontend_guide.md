# Frontend Guide — Django + Next.js AI Chatbot

> A practical reference for how the Next.js frontend is structured, how to navigate it, and how to add things.

---

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Framework | Next.js (App Router) | 16.2.6 |
| Language | JavaScript (ES Modules) | — |
| UI | React | 19.2.6 |
| Styling | Tailwind CSS | 4.3.0 |
| Auth | BFF Proxy (HttpOnly cookies) | — |
| Testing | Vitest | 4.1.7 |
| Testing Utils | Testing Library (React, DOM, User Event) | — |
| Linting | ESLint (flat config) | 9 |
| Fonts | Geist + Geist Mono (`next/font/google`) | — |

---

## Project Structure

```
frontend/
├── app/                        # Next.js App Router pages
│   ├── layout.js               # Root layout (fonts, metadata, globals)
│   ├── page.js                 # Home page (stub — still default scaffold)
│   ├── globals.css             # Tailwind v4 import + CSS custom properties
│   ├── favicon.ico             # Browser tab icon
│   │
│   ├── login/                  # ❌ TODO — Login page
│   │   └── page.jsx
│   │
│   ├── (app)/                  # ❌ TODO — Authenticated route group
│   │   ├── layout.jsx          #   Protected layout with session check
│   │   ├── chat/
│   │   │   └── page.jsx        #   Chat interface
│   │   ├── documents/
│   │   │   └── page.jsx        #   Document management
│   │   ├── settings/
│   │   │   └── page.jsx        #   User preferences
│   │   └── analytics/
│   │       └── page.jsx        #   Token usage & costs
│   │
│   └── api/
│       ├── auth/
│       │   ├── login/route.js      # ❌ TODO — Login proxy → Django
│       │   ├── refresh/route.js    # ❌ TODO — Token refresh proxy
│       │   ├── logout/route.js     # ❌ TODO — Logout + blacklist proxy
│       │   └── me/route.js         # ❌ TODO — Current user proxy
│       └── proxy/
│           └── [...path]/route.js  # ❌ TODO — Generic API proxy
│
├── components/                 # ❌ TODO — Reusable UI components
│   ├── ui/                     #   Buttons, inputs, cards, modals
│   ├── chat/                   #   Chat-specific (message bubble, input bar)
│   └── layout/                 #   Sidebar, header, nav
│
├── lib/                        # ❌ TODO — Shared utilities
│   ├── api.js                  #   Server-side fetch (reads cookies, injects Bearer)
│   ├── api-client.js           #   Client-side fetch (calls /api/proxy/...)
│   ├── cookies.js              #   Cookie constants: names, max-ages, options
│   └── ws.js                   #   (Phase 2) WebSocket with auth frame
│
├── hooks/                      # ❌ TODO — Custom React hooks
│   ├── useChat.js              #   Chat message state + streaming
│   └── useWebSocket.js         #   WebSocket connection lifecycle (auth frame)
│
├── __tests__/                  # ❌ TODO — Test files
│   ├── auth.test.js
│   ├── middleware.test.js
│   └── chat.test.js
│
├── public/                     # Static assets (served as-is)
│   ├── file.svg
│   ├── globe.svg
│   ├── next.svg
│   ├── vercel.svg
│   └── window.svg
│
├── docs/                       # Documentation
│   ├── frontend_guide.md       # ← this file
│   ├── current_status.md       # What's done, what's next
│   ├── vision.md               # Project direction and goals
│   └── AUTHJS_INTEGRATION.md   # Auth.js v5 implementation playbook
│
├── next.config.mjs             # Next.js configuration
├── postcss.config.mjs          # PostCSS with @tailwindcss/postcss plugin
├── eslint.config.mjs           # ESLint flat config (eslint-config-next)
├── jsconfig.json               # Path alias @/* → ./*
├── vitest.config.mjs           # ❌ TODO — Vitest configuration
├── middleware.js                # ❌ TODO — Route protection (cookie existence check)
├── auth.js                     # (not needed — removed from stack)
├── .env.local                  # Environment variables (gitignored)
├── .env.example                # Template for environment variables
├── Dockerfile                  # Dev-mode Docker image
└── package.json
```

---

## Environment Variables

| Variable | Example | Used by |
|----------|---------|---------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000/api/v1` | API calls to Django backend |
| `INTERNAL_API_URL` | `http://localhost:8000/api/v1` | Server-side API base (differs in Docker/production) |
| `NEXT_PUBLIC_BASE_URL` | `http://localhost:8000` | Base backend URL (media, static) |
| `NEXT_PUBLIC_WS_HOST` | `localhost:8000` | WebSocket connection host |
| `NODE_ENV` | `development` | Next.js environment mode |

> ⚠️ **Never commit `.env.local`!** Copy `.env.example` and fill in real values.

---

## Styling — Tailwind CSS v4

This project uses **Tailwind CSS v4** with the new CSS-first configuration. There is **no `tailwind.config.js`** — all configuration happens in `globals.css`.

### How It Works

```css
/* app/globals.css */
@import "tailwindcss";           /* ← v4 import (replaces @tailwind directives) */

@theme inline {                  /* ← v4 theme configuration */
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --font-sans: var(--font-geist-sans);
  --font-mono: var(--font-geist-mono);
}
```

### Adding Custom Theme Values

Extend the `@theme inline` block in `globals.css`:

```css
@theme inline {
  --color-primary: #3b82f6;
  --color-secondary: #8b5cf6;
  --color-accent: #06b6d4;
}
```

Then use in components:

```jsx
<div className="bg-primary text-accent">Styled!</div>
```

### Dark Mode

Currently uses `prefers-color-scheme: dark` (system preference). To add manual toggle later, extend the CSS with a class-based strategy.

---

## Routing — App Router

Next.js 16 uses the **App Router** (no `pages/` directory). Key concepts:

### Route Groups

```
app/
├── (app)/              # ← Route group (parentheses = no URL segment)
│   ├── layout.jsx      #   Shared layout for authenticated pages
│   └── chat/
│       └── page.jsx    #   → /chat
├── login/
│   └── page.jsx        #   → /login
└── api/
    ├── auth/
    │   ├── login/       #   → /api/auth/login
    │   ├── refresh/     #   → /api/auth/refresh
    │   └── logout/      #   → /api/auth/logout
    └── proxy/
        └── [...path]/   #   → /api/proxy/*
```

- `(app)/` is a route group — the parentheses mean it doesn't add to the URL path
- Each `page.js` file becomes a route
- Each `layout.js` wraps its children with shared UI

### Server vs Client Components

```jsx
// Default = Server Component (no "use client")
// Good for: data fetching, static content, SEO

// app/(app)/chat/page.jsx
import { apiFetch } from "@/lib/api";

export default async function ChatPage() {
  const sessions = await apiFetch("/chat/sessions/");  // reads cookie server-side
  // ...
}

// ---
// Client Component = add "use client" at top
// Good for: interactivity, hooks, browser APIs

// components/chat/message-input.jsx
"use client";

import { useState } from "react";

export default function MessageInput() {
  const [message, setMessage] = useState("");
  // ...
}
```

### API Routes

```jsx
// app/api/auth/login/route.js — Login proxy
import { NextResponse } from "next/server";

export async function POST(request) {
  const { email, password } = await request.json();
  // Call Django, set httpOnly cookies, return user data
}

// app/api/proxy/[...path]/route.js — Generic API proxy
export async function GET(request, { params }) {
  // Read access_token cookie, inject Bearer header, forward to Django
}
```

---

## Authentication — BFF Proxy Pattern

The frontend uses a **Backend-for-Frontend (BFF)** proxy pattern for authentication. No third-party auth library sits between Next.js and Django. Django remains the sole identity authority.

### Architecture

```
Browser → middleware.js (cookie existence check)
         → Route Handlers (login, refresh, logout, proxy)
         → Django backend /api/v1/auth/* (token generation)
         → httpOnly cookies (access_token, refresh_token)
```

### Key Files (to be created)

| File | Purpose |
|------|---------|
| `middleware.js` | Route protection — redirect if no access_token cookie |
| `app/api/auth/login/route.js` | Login proxy — calls Django, sets httpOnly cookies |
| `app/api/auth/refresh/route.js` | Refresh proxy — reads refresh cookie, calls Django, updates cookies |
| `app/api/auth/logout/route.js` | Logout proxy — blacklists token on Django, clears cookies |
| `app/api/proxy/[...path]/route.js` | Generic API proxy — reads cookie, injects Bearer header, forwards to Django |
| `lib/cookies.js` | Cookie names, max-ages, options — single source of truth |

### Integration with Django

```
Login Flow:
    Browser → POST /api/auth/login (email, password)
            → Next.js Route Handler
            → POST Django /api/v1/auth/token/
            → Django returns { access, refresh }
            → Next.js sets httpOnly cookies (NO tokens in response body)

Authenticated Request:
    Browser → GET /api/proxy/chat/sessions/
            → Next.js reads access_token cookie
            → Injects Authorization: Bearer <token>
            → Forwards to Django /api/v1/chat/sessions/
            → Returns response to browser
```

> Full implementation playbook: `docs/AUTHJS_INTEGRATION.md`

---

## API Layer (To Be Built)

### Architecture

```
Client Component → /api/proxy/... → Next.js Route Handler → Django Backend /api/v1/...
Server Component → lib/api.js → Django Backend /api/v1/... (reads cookies directly)
```

### Pattern — Client Components

```jsx
// Client components call the proxy — no token handling needed
const res = await fetch("/api/proxy/chat/sessions/");
const sessions = await res.json();
```

### Pattern — Server Components

```jsx
// lib/api.js — reads access_token cookie, injects Bearer header
import { cookies } from "next/headers";

const API_URL = process.env.INTERNAL_API_URL;

export async function apiFetch(path, options = {}) {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get("access_token")?.value;

  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
      ...options.headers,
    },
  });

  if (!res.ok) throw new ApiError(res.status, await res.json());
  return res.json();
}
```

---

## Testing — Vitest + Testing Library

### Setup (to be created)

```js
// vitest.config.mjs
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./__tests__/setup.js"],
    globals: true,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
});
```

### Running Tests

```bash
npm run test              # Single run
npm run test:watch        # Watch mode
npm run test:coverage     # With coverage report
```

### Testing Patterns

```jsx
// __tests__/components/chat-message.test.jsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect } from "vitest";
import ChatMessage from "@/components/chat/message-bubble";

describe("ChatMessage", () => {
  it("renders message text", () => {
    render(<ChatMessage role="user" content="Hello!" />);
    expect(screen.getByText("Hello!")).toBeInTheDocument();
  });
});
```

---

## Adding a New Page

1. **Create the page file** — `app/(app)/my-feature/page.jsx`
2. **Create components** — `components/my-feature/`
3. **Add lib functions** — `lib/my-feature.js`
4. **Add tests** — `__tests__/my-feature.test.jsx`
5. **Update nav** — Add link in `components/layout/sidebar.jsx`

```jsx
// app/(app)/my-feature/page.jsx
import { apiFetch } from "@/lib/api";

export default async function MyFeaturePage() {
  const data = await apiFetch("/my-feature/");

  return (
    <div>
      <h1 className="text-2xl font-bold">My Feature</h1>
      {/* ... */}
    </div>
  );
}
```

---

## Key Commands

```bash
npm run dev              # Dev server with Turbopack (localhost:3000)
npm run build            # Production build
npm run start            # Start production server
npm run lint             # ESLint check
npm run test             # Vitest single run
npm run test:watch       # Vitest watch mode
npm run test:coverage    # Vitest with coverage
```

---

## Connecting to the Backend

The frontend connects to the Django backend at `NEXT_PUBLIC_API_URL` (default: `http://localhost:8000/api/v1`).

| Frontend Action | Backend Endpoint |
|----------------|-----------------|
| Login | `POST /api/v1/auth/login/` |
| Register | `POST /api/v1/auth/register/` |
| Get sessions | `GET /api/v1/chat/sessions/` |
| Send message | `POST /api/v1/chat/sessions/{id}/messages/` |
| Upload document | `POST /api/v1/chat/documents/` |
| Get preferences | `GET /api/v1/chat/preferences/me/` |
| WebSocket stream | `ws://localhost:8000/ws/chat/{session_id}/` |

> Backend API docs: http://localhost:8000/api/v1/docs/ (Swagger UI)
