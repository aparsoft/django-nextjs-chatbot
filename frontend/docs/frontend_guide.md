# Frontend Guide — ConvoInsight AI Chatbot

> A practical reference for how the Next.js frontend is structured, how to navigate it, and how to add things.

---

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Framework | Next.js (App Router) | 16.2.6 |
| Language | JavaScript (ES Modules) | — |
| UI | React | 19.2.6 |
| Styling | Tailwind CSS | 4.3.0 |
| Auth | NextAuth.js v5 (Auth.js) | 5.0.0-beta.31 |
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
│       └── auth/
│           └── [...nextauth]/  # ❌ TODO — Auth.js catch-all route handler
│               └── route.js
│
├── components/                 # ❌ TODO — Reusable UI components
│   ├── ui/                     #   Buttons, inputs, cards, modals
│   ├── chat/                   #   Chat-specific (message bubble, input bar)
│   └── layout/                 #   Sidebar, header, nav
│
├── lib/                        # ❌ TODO — Shared utilities
│   ├── api.js                  #   Axios/fetch wrapper with JWT refresh
│   ├── auth-client.js          #   Client-side auth helpers
│   └── ws.js                   #   WebSocket connection manager
│
├── hooks/                      # ❌ TODO — Custom React hooks
│   ├── useChat.js              #   Chat message state + streaming
│   ├── useAuth.js              #   Session access shortcut
│   └── useWebSocket.js         #   WebSocket connection lifecycle
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
├── middleware.js                # ❌ TODO — Auth.js route protection
├── auth.js                     # ❌ TODO — Auth.js configuration
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
| `NEXT_PUBLIC_BASE_URL` | `http://localhost:8000` | Base backend URL (media, static) |
| `NEXT_PUBLIC_WS_HOST` | `localhost:8000` | WebSocket connection host |
| `AUTH_SECRET` | *(generate with `openssl rand -base64 32`)* | Auth.js session encryption |
| `AUTH_TRUST_HOST` | `true` | Trust the host in auth callbacks |
| `AUTH_URL` | `http://localhost:3000` | Canonical auth callback URL |
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
    └── auth/
        └── [...nextauth]/   #   → /api/auth/*
```

- `(app)/` is a route group — the parentheses mean it doesn't add to the URL path
- Each `page.js` file becomes a route
- Each `layout.js` wraps its children with shared UI

### Server vs Client Components

```jsx
// Default = Server Component (no "use client")
// Good for: data fetching, static content, SEO

// app/chat/page.jsx
import { auth } from "@/auth";

export default async function ChatPage() {
  const session = await auth();  // Server-side session check
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
// app/api/auth/[...nextauth]/route.js
import { handlers } from "@/auth";

export const { GET, POST } = handlers;
```

---

## Authentication — NextAuth.js v5

Auth.js v5 provides server-side session management, eliminating localStorage JWT tokens (XSS vulnerability).

### Architecture

```
Browser → middleware.js (route guard)
         → auth.js (session config)
         → Django backend /api/v1/auth/login/ (Credentials verification)
         → JWT session cookie (httpOnly, secure)
```

### Key Files (to be created)

| File | Purpose |
|------|---------|
| `auth.js` | Auth.js configuration — Credentials provider, JWT callbacks, Django backend adapter |
| `middleware.js` | Route protection — redirect unauthenticated users to `/login` |
| `app/api/auth/[...nextauth]/route.js` | Catch-all route handler for auth endpoints |
| `lib/auth-client.js` | Client-side helpers (`signIn`, `signOut`, `useSession`) |

### Integration with Django

```
NextAuth Credentials Provider
    │
    ▼ authorize(credentials)
    │
    ▼ POST http://localhost:8000/api/v1/auth/login/
    │   { email, password }
    │
    ▼ Django returns { access, refresh }
    │
    ▼ JWT callback stores tokens in session
    │
    ▼ Session cookie set (httpOnly)
```

> Full implementation playbook: `docs/AUTHJS_INTEGRATION.md`

---

## API Layer (To Be Built)

### Architecture

```
Component → lib/api.js → Django Backend /api/v1/
```

### Pattern

```jsx
// lib/api.js
const API_URL = process.env.NEXT_PUBLIC_API_URL;

export async function apiFetch(path, options = {}) {
  const session = await auth();  // Server-side
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${session.accessToken}`,
      ...options.headers,
    },
  });

  if (!res.ok) throw new ApiError(res.status, await res.json());
  return res.json();
}

// Usage in server component:
const sessions = await apiFetch("/chat/sessions/");
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
import { auth } from "@/auth";
import { apiFetch } from "@/lib/api";

export default async function MyFeaturePage() {
  const session = await auth();
  if (!session) return null;

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
