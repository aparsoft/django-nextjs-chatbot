# Authentication Playbook — BFF Proxy Pattern

> A step-by-step doc for interns to implement **Backend-for-Frontend (BFF) Proxy** authentication between the Next.js frontend and Django JWT backend. No code is included on purpose: this is the **plan**. You write the code.
>
> When you finish, the frontend will store tokens in **HttpOnly cookies** managed by Next.js Route Handlers. Django remains the sole identity authority. No third-party auth library sits between them.

---

## 0. Why This Architecture (Not Auth.js)

### What's Wrong with Auth.js v5 + Django SimpleJWT?

Auth.js v5 is an excellent tool when Next.js talks directly to a database (Prisma/Drizzle) or acts as an OAuth client (Google, GitHub). But pairing it with Django SimpleJWT via the Credentials Provider creates **three production landmines**:

**1. The Race Condition**

Next.js App Router renders multiple Server Components in parallel. When an access token expires, each component independently triggers Auth.js's `jwt()` callback, which fires concurrent refresh requests to Django using the **same** refresh token. With `BLACKLIST_AFTER_ROTATION = True`, Django blacklists the old token after the first refresh — the second and third requests hit a blacklisted token and the user gets kicked out.

This is a **confirmed, widely reported bug** — not a theory:
- [Stack Overflow: Race Condition During Access Token Refresh with NextAuth.js v5](https://stackoverflow.com/questions/79578846/race-condition-during-access-token-refresh-with-nextauth-js-v5-server-side)
- [GitHub Discussions nextauthjs/next-auth #3940](https://github.com/nextauthjs/next-auth/discussions/3940)
- [Reddit r/nextjs: Token Refresh Race Condition](https://www.reddit.com/r/nextjs/comments/1cqgnxp/token_refresh_race_condition_issue_with_authjs/)

**2. The JWE Bloat**

Auth.js doesn't just put your Django JWT in a cookie. It serializes it, encrypts it inside its own JWE (JSON Web Encryption) wrapper, and decrypts it on every single request. You're paying a cryptographic tax to manage a token that Django already cryptographically secured.

**3. Loss of Cookie Control**

Auth.js abstracts cookie management away. Modifying cookies dynamically from middleware (e.g., setting custom max-ages, responding to Django rotation signals) requires returning modified token objects from callbacks and hoping the internal engine flushes them correctly.

### Why BFF Proxy Is the Right Choice

| Concern | Auth.js v5 (Credentials + Django) | BFF Proxy Pattern |
|---|---|---|
| **Token storage** | Django tokens double-wrapped inside Auth.js JWE cookie | Single `httpOnly` cookie per token. Raw JWTs. |
| **Concurrency** | Parallel `jwt()` callbacks cause race conditions on token rotation | Each proxy request is independent; refresh lock is simple |
| **Performance** | Cryptographic decrypt/encrypt on every request | Zero overhead. Just forwarding strings. |
| **Cookie control** | Abstracted; must return objects from callbacks | Direct `cookies()` API. Full control. |
| **Mobile compatibility** | Auth.js is web-only; Django must serve mobile separately | Django API stays unified — mobile uses tokens directly |
| **Complexity** | `authorize`, `jwt`, `session` callbacks to sync two systems | A few Route Handlers that proxy to Django |

**The rule:** Django is already your auth database and token generator. Don't wrap it in another abstraction that tries to manage state Django already manages.

---

## 1. The Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                       Browser                                    │
│                                                                  │
│   Client Components ──► fetch('/api/proxy/...')                  │
│                          (cookies sent automatically)            │
│                                                                  │
│   httpOnly cookies:                                              │
│     • access_token  (short-lived, ~5 min)                        │
│     • refresh_token (long-lived, ~1 day)                         │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Next.js BFF Layer                              │
│                                                                  │
│   ┌────────────────────────────────────────────────────────┐     │
│   │  middleware.js (or proxy.js in Next.js 16)             │     │
│   │  • Checks if access_token cookie exists                │     │
│   │  • Redirects to /login if missing                      │     │
│   │  • Does NOT validate token (that's the route handler)  │     │
│   └──────────────────────────┬─────────────────────────────┘     │
│                              │                                   │
│   ┌──────────────────────────▼─────────────────────────────┐     │
│   │  Route Handlers (app/api/)                              │     │
│   │                                                         │     │
│   │  /api/auth/login   → POST Django /auth/token/          │     │
│   │                      Set httpOnly cookies               │     │
│   │                                                         │     │
│   │  /api/auth/refresh → POST Django /auth/token/refresh/  │     │
│   │                      Update cookies                     │     │
│   │                                                         │     │
│   │  /api/auth/logout  → POST Django /auth/token/blacklist/│     │
│   │                      Clear cookies                      │     │
│   │                                                         │     │
│   │  /api/proxy/[...path] → Read access_token cookie       │     │
│   │                          Inject Authorization header    │     │
│   │                          Forward to Django              │     │
│   └──────────────────────────┬─────────────────────────────┘     │
│                              │                                   │
│   ┌──────────────────────────▼─────────────────────────────┐     │
│   │  Server Components                                      │     │
│   │  • Read cookies via cookies()                           │     │
│   │  • Call lib/api.js which uses the proxy                 │     │
│   │  • Or call Django directly with the token               │     │
│   └────────────────────────────────────────────────────────┘     │
│                                                                  │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                     Django Backend (unchanged)                    │
│                                                                  │
│   POST /api/v1/auth/token/           → { access, refresh }      │
│   POST /api/v1/auth/token/refresh/   → { access, refresh }      │
│   POST /api/v1/auth/token/blacklist/ → 200                      │
│   GET  /api/v1/users/me/             → current user             │
│   GET  /api/v1/*                     → resource APIs            │
│   WS   ws/chat/{session_id}/         → WebSocket consumers      │
│                                                                  │
│   Django does not know or care that Next.js is a proxy.          │
│   It sees standard JWT Bearer requests.                          │
└──────────────────────────────────────────────────────────────────┘
```

### Key Principle

The browser **never talks to Django directly**. Every authenticated request goes through the Next.js BFF layer. The browser only sees:
- `httpOnly` cookies it can't read (XSS protection)
- Same-origin requests (no CORS issues)
- Tokens it never sees in JavaScript

The Django API remains **unified** — the React Native mobile app talks to the same endpoints directly using tokens in secure storage (iOS Keychain / Android Keystore).

---

## 2. Prerequisites

- Backend running on `http://localhost:8000`.
- `next-auth` has been **removed** from `package.json` (it's not needed).

### Environment Variables

Update `frontend/.env.local`:

| Variable | Example | Purpose |
|----------|---------|---------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000/api/v1` | Public-facing API base (used in client components for WS URLs, etc.) |
| `INTERNAL_API_URL` | `http://localhost:8000/api/v1` | Server-side API base. Same in dev; different in Docker/production where Next.js and Django are on different networks. |
| `NEXT_PUBLIC_WS_HOST` | `localhost:8000` | WebSocket host |
| `AUTH_TRUST_HOST` | `true` | Trust the host behind a reverse proxy |

> ⚠️ **No `AUTH_SECRET` needed.** We're not encrypting cookies with a framework secret. The tokens are already cryptographically signed by Django.

Document every new env var in `frontend/.env.example`.

---

## 3. Files You Will Create

```
frontend/
├── middleware.js                            # Route protection (checks cookie existence)
├── app/
│   ├── api/
│   │   ├── auth/
│   │   │   ├── login/
│   │   │   │   └── route.js                # Login proxy → Django
│   │   │   ├── refresh/
│   │   │   │   └── route.js                # Refresh proxy → Django (with lock)
│   │   │   ├── logout/
│   │   │   │   └── route.js                # Logout proxy → Django blacklist
│   │   │   └── me/
│   │   │       └── route.js                # Current user proxy → Django
│   │   └── proxy/
│   │       └── [...path]/
│   │           └── route.js                # Generic API proxy (catch-all)
│   ├── login/
│   │   └── page.jsx                        # Login form (calls /api/auth/login)
│   └── (app)/                              # Authenticated route group
│       ├── layout.jsx                      # Server component: validates session
│       ├── chat/
│       │   └── page.jsx
│       ├── documents/
│       │   └── page.jsx
│       └── settings/
│           └── page.jsx
├── lib/
│   ├── api.js                              # Server-side fetch helper (reads cookies)
│   ├── api-client.js                       # Client-side fetch helper (calls proxy)
│   ├── cookies.js                          # Cookie constants: names, options, helpers
│   └── ws.js                               # (Phase 2) WebSocket with auth frame
└── __tests__/
    ├── auth/
    │   ├── login.test.js                   # Login route handler tests
    │   ├── refresh.test.js                 # Refresh route handler tests (with lock)
    │   ├── logout.test.js                  # Logout route handler tests
    │   └── proxy.test.js                   # Proxy route handler tests
    └── middleware.test.js                  # Route protection tests
```

---

## 4. Step-by-Step Implementation Plan

Work in this order. Do not skip ahead. Each step ends with a verifiable outcome.

### Step 1 — Cookie Constants (`lib/cookies.js`)

Create a central module that defines cookie names, max-ages, and cookie options. This avoids magic strings scattered across the codebase.

```js
// This is the ONLY place cookie names are defined.
// Every other file imports from here.

export const ACCESS_TOKEN_COOKIE = "access_token";
export const REFRESH_TOKEN_COOKIE = "refresh_token";

// Match your Django SIMPLE_JWT settings:
// ACCESS_TOKEN_LIFETIME = timedelta(minutes=5)
// REFRESH_TOKEN_LIFETIME = timedelta(days=1)
export const ACCESS_MAX_AGE = 5 * 60;          // 5 minutes (seconds)
export const REFRESH_MAX_AGE = 24 * 60 * 60;   // 1 day (seconds)

export const cookieOptions = {
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "strict",
  path: "/",
};
```

**Verify:** `npm run build` passes.

---

### Step 2 — Login Route Handler (`app/api/auth/login/route.js`)

This is the BFF login endpoint. The browser sends email + password here. The handler:
1. Validates input
2. Calls Django's `/api/v1/auth/token/` with the credentials
3. On success, sets both tokens as `httpOnly` cookies
4. Returns user data (NO tokens in the response body)

The client **never sees** the raw JWT strings.

**Verify:** `curl -X POST http://localhost:3000/api/auth/login -H 'Content-Type: application/json' -d '{"email":"admin@aparsoft.com","password":"test123"}'` returns user data and sets cookies. The response body must NOT contain `access` or `refresh`.

---

### Step 3 — Refresh Route Handler (`app/api/auth/refresh/route.js`)

This is the most critical handler. It reads the `refresh_token` cookie, calls Django's refresh endpoint, and updates both cookies.

**The Concurrency Lock:**

Unlike Auth.js's `jwt()` callback which fires independently per Server Component, this route handler is a single HTTP endpoint. But if two client-side requests trigger refresh simultaneously, we still need a lock.

Use a **module-scoped Promise lock**:

```js
let refreshPromise = null;

export async function POST(request) {
  // If a refresh is already in flight, await it instead of firing another
  if (!refreshPromise) {
    refreshPromise = doRefresh(request).finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}
```

This ensures that even if 5 requests hit `/api/auth/refresh` at the same millisecond, only **one** Django refresh call is made. The rest await the same result.

> ⚠️ **Important:** This lock is process-scoped (single Node.js instance). In a serverless deployment with multiple instances, you'd need a distributed lock (Redis). For this project (single server / Docker), the process lock is sufficient.

**Verify:** Use browser DevTools to manually expire the access token. A page with 3 parallel Server Components should all succeed without any `401` errors.

---

### Step 4 — Logout Route Handler (`app/api/auth/logout/route.js`)

1. Read the `refresh_token` cookie.
2. `POST` to Django's `/api/v1/auth/token/blacklist/` with the refresh token.
3. Clear both cookies (`maxAge: -1` or `expires: new Date(0)`).
4. Return success.

**Verify:** After logout, cookies are gone and Django admin shows the token blacklisted.

---

### Step 5 — Current User Route (`app/api/auth/me/route.js`)

1. Read the `access_token` cookie.
2. If missing, try refreshing first (call the refresh logic).
3. `GET` Django's `/api/v1/users/me/` with the access token.
4. Return the user object.

Client components call this to check auth status without talking to Django directly.

**Verify:** `curl -b "access_token=..." http://localhost:3000/api/auth/me` returns user data.

---

### Step 6 — Generic API Proxy (`app/api/proxy/[...path]/route.js`)

This is the **catch-all proxy** that forwards any API request to Django.

1. Read the `access_token` cookie.
2. If expired (decode JWT `exp` claim), refresh first.
3. Inject `Authorization: Bearer <token>` header.
4. Forward the request to `INTERNAL_API_URL + path`.
5. Return Django's response to the client.

This means client components never need to handle tokens at all:

```js
// Client component — no token handling needed!
const res = await fetch("/api/proxy/chat/sessions/");
const sessions = await res.json();
```

The proxy handles auth transparently.

**Verify:** From a logged-in browser, `fetch('/api/proxy/users/me/').then(r => r.json())` returns user data.

---

### Step 7 — Middleware (`middleware.js`)

Create `middleware.js` at the project root. This is the **first line of defense** — a bouncer that checks if you have a ticket.

1. Check if `access_token` cookie exists.
2. If missing, redirect to `/login`.
3. If present, let the request through.

> ⚠️ **Middleware does NOT validate the token.** It only checks cookie existence. Token validation happens server-side in the route handlers and layouts. Think of middleware as a bouncer checking if you have a ticket, while your server components verify the ticket is valid.

```js
// middleware.js
import { NextResponse } from "next/server";
import { ACCESS_TOKEN_COOKIE } from "@/lib/cookies";

export function middleware(request) {
  const accessToken = request.cookies.get(ACCESS_TOKEN_COOKIE);

  if (!accessToken) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("callbackUrl", request.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!login|api/auth|_next/static|_next/image|favicon.ico|public).*)",
  ],
};
```

**Note on Next.js 16 Proxy API:** Next.js 16 introduces `proxy.js` as a replacement for `middleware.js`. It provides the same functionality with direct access to the request object. For now, `middleware.js` works perfectly and has more community documentation. The migration to `proxy.js` is a future PR — the patterns are identical.

**Verify:** Visit `http://localhost:3000/chat` without being logged in. You should be redirected to `/login?callbackUrl=/chat`.

---

### Step 8 — Login Page (`app/login/page.jsx`)

A client component that:
1. Renders an email/password form.
2. On submit, `POST` to `/api/auth/login`.
3. On success, redirect to the `callbackUrl` search param (or `/chat`).
4. On failure, show error message.
5. No `localStorage`. No tokens in JavaScript. The login response sets cookies server-side.

**Verify:** Log in. DevTools → Application → Cookies shows `access_token` and `refresh_token` as `httpOnly`. DevTools → Application → Local Storage is empty.

---

### Step 9 — Server-Side API Helper (`lib/api.js`)

A helper for **Server Components** to call Django directly (not through the proxy — they're already on the server):

1. Read `access_token` from `cookies()`.
2. If expired, call `/api/auth/refresh` internally or refresh directly.
3. Make the fetch to Django with `Authorization: Bearer <token>`.
4. Return the response.

```js
// Usage in a Server Component:
import { apiFetch } from "@/lib/api";

export default async function ChatPage() {
  const sessions = await apiFetch("/chat/sessions/");
  return <SessionList sessions={sessions} />;
}
```

---

### Step 10 — Authenticated Route Group (`app/(app)/`)

1. Create `app/(app)/layout.jsx` as a **server component**.
2. Read the `access_token` cookie.
3. Validate it by calling `/api/auth/me` (or directly calling Django's `/users/me/`).
4. If invalid, `redirect('/login')`.
5. Render the sidebar + header + children.

This is the **second line of defense** (belt-and-braces after middleware):
- **Middleware:** Fast cookie-existence check (runs at the edge, every request)
- **Layout:** Full token validation (runs server-side, page loads only)

**Verify:** Logged-in users see the app. Logged-out users get redirected by middleware BEFORE the page renders (no flash of protected content).

---

### Step 11 — WebSocket Authentication (Phase 2 Preparation)

Do NOT pass tokens in WebSocket URL query parameters (`?token=<access>`). Query parameters are logged in plaintext by reverse proxies, load balancers, and web servers.

Instead, use the **auth frame pattern**:

1. Establish the WebSocket connection (no token in URL).
2. Immediately send an auth frame as the first message: `{ type: "auth", token: "<access>" }`
3. Server validates the token. If valid, the connection stays open. If not, close it.

The Server Component or Route Handler reads the `access_token` cookie and provides it to the client component via a prop or an API endpoint. The client component never reads the cookie directly.

Document this pattern in `lib/ws.js` as a TODO for Phase 2.

---

### Step 12 — Tests

Add the following Vitest tests:

| Test File | What It Tests |
|-----------|--------------|
| `__tests__/auth/login.test.js` | Login handler: success sets cookies, failure returns error, missing fields rejected |
| `__tests__/auth/refresh.test.js` | Refresh handler: successful refresh, expired refresh token, **concurrency lock** (3 parallel calls → 1 Django request) |
| `__tests__/auth/logout.test.js` | Logout handler: clears cookies, calls Django blacklist |
| `__tests__/auth/proxy.test.js` | Proxy handler: injects auth header, handles 401, handles missing cookie |
| `__tests__/middleware.test.js` | Middleware: redirects without cookie, passes with cookie, respects public routes |

**Verify:** `npm run test` passes with coverage for all auth route handlers.

---

### Step 13 — Documentation Sweep

In the same PR, update:

- `frontend/docs/frontend_guide.md` — auth section updated to BFF pattern
- `frontend/docs/current_status.md` — mark auth as "BFF Proxy pattern"
- `frontend/.env.example` — updated env vars (remove `AUTH_SECRET`, add `INTERNAL_API_URL`)

**Verify:** No mention of `next-auth`, `Auth.js`, `useSession`, `signIn`, or `authjs` remains anywhere under `frontend/`.

---

## 5. Architectural Rules This Implementation Locks In

Once the BFF proxy is in place, these become non-negotiable in code review:

1. **No direct token storage.** The frontend never writes to `localStorage` or `sessionStorage` for auth.
2. **No third-party auth library.** Django is the identity authority. Next.js is a proxy. Nothing sits between them.
3. **All authenticated requests go through the proxy.** Client components call `/api/proxy/...`. Server components use `lib/api.js`.
4. **Route protection is two-layer.** Middleware checks cookie existence (fast, edge). Layout validates the token (server-side, accurate).
5. **Refresh has a lock.** The refresh route handler uses a process-scoped promise lock to prevent concurrent Django refresh calls.
6. **Tokens are never in URLs.** WebSocket auth uses the auth frame pattern, not query parameters.
7. **Django API stays unified.** The same Django endpoints serve both the Next.js web client and the React Native mobile client. No special cookie-auth backend needed.

---

## 6. Pitfalls to Avoid

| Pitfall | The Fix |
|---------|---------|
| **Middleware validates tokens** | Middleware only checks cookie existence. Validation happens in route handlers and layouts. |
| **Refresh race condition** | The module-scoped promise lock in `/api/auth/refresh` prevents concurrent Django calls. |
| **`BLACKLIST_AFTER_ROTATION`** | In Django settings, either: (a) set `BLACKLIST_AFTER_ROTATION = False` and use short-lived refresh tokens, or (b) keep it `True` and ensure the BFF lock is solid. Option (a) is simpler for this project. |
| **Cookies not set in production** | Ensure `secure: true` and `sameSite: "strict"` in production. Check that the domain matches. |
| **Server fetch URL in Docker** | Use `INTERNAL_API_URL` for server-side calls (Docker network), `NEXT_PUBLIC_API_URL` for client-side (browser). |
| **Large cookie payload** | Keep cookies to just the JWT strings. No user objects — fetch user data from `/api/auth/me`. |
| **Stale access token in proxy** | The proxy should decode the JWT `exp` claim and refresh proactively before forwarding, not wait for a 401. |
| **Forgetting to clear cookies on logout** | Always clear both `access_token` and `refresh_token` cookies, even if the Django blacklist call fails. |
| **WebSocket token in URL** | Never. Use the auth frame pattern. URL query params are logged by every proxy in the chain. |

---

## 7. How You'll Know You're Done

Tick this list before opening the PR.

- [ ] `npm run build && npm run test` are green.
- [ ] `next-auth` is removed from `package.json`. (`grep -r "next-auth" frontend/ --include="*.js" --include="*.json"` returns nothing.)
- [ ] No `localStorage` / `sessionStorage` access for auth. (`grep -rn "localStorage" frontend/app frontend/lib` returns nothing auth-related.)
- [ ] Login sets `httpOnly` cookies. No tokens in response body or JavaScript.
- [ ] Middleware redirects unauthenticated users to `/login?callbackUrl=...`.
- [ ] After 5 minutes idle, a page with multiple Server Components still loads — the refresh lock handled the rotation silently.
- [ ] Logout clears both cookies and blacklists the token on Django.
- [ ] WebSocket auth uses the auth frame pattern, not URL parameters (documented, not implemented until Phase 2).
- [ ] All docs updated. No mention of Auth.js remains.

---

## 8. After This PR

Two follow-ups are queued, not in scope here:

1. **`lib/ws.js`** in Phase 2 implements WebSocket auth using the auth frame pattern. The access token is read from cookies server-side and passed as the first frame over the established connection.
2. **Migrate to `proxy.js`** — Next.js 16 introduces a native Proxy API that replaces `middleware.js`. The patterns are identical; the migration is mechanical. Do this when `proxy.js` has more community documentation and examples.

---

## 9. Reference Reading

- [Dev.to: BFF Pattern with Next.js API Routes](https://dev.to/favour_okpara_9dc22591b2f/implementing-secure-authentication-in-nextjs-with-external-apis-a-bff-pattern-approach-hmg) — the pattern this playbook is based on
- [Medium: BFF Pattern with Next.js API Routes](https://medium.com/digigeek/bff-backend-for-frontend-pattern-with-next-js-api-routes-secure-and-scalable-architecture-d6e088a39855)
- [Reddit: Best way to handle JWT auth (Next.js + Django)](https://www.reddit.com/r/nextjs/comments/1nygfcn/best_way_to_handle_jwt_auth_nextjs_django/)
- [Next.js 16 Proxy vs Middleware BFF Guide](https://u11d.com/blog/nextjs-16-proxy-vs-middleware-bff-guide/) — the new `proxy.js` convention
- [Stack Overflow: Race Condition with NextAuth.js v5](https://stackoverflow.com/questions/79578846/race-condition-during-access-token-refresh-with-nextauth-js-v5-server-side) — why we're not using Auth.js
- [GitHub: nextjs-django-jwt-auth](https://github.com/FlorianMgs/nextjs-django-jwt-auth) — reference implementation
- Django SimpleJWT docs: https://django-rest-framework-simplejwt.readthedocs.io/

---

That is the whole plan. When you have shipped it, the frontend has a production-grade auth architecture that is simple, secure, and maintainable — with no abstraction bloat between Next.js and Django.
