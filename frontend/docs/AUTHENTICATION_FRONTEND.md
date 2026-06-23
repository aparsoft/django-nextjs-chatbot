# Authentication Playbook — Production-Grade BFF Proxy (Next.js 16 + Django DRF)

> A complete, copy-pasteable guide for interns to build a **production-grade** authentication system using the **Backend-for-Frontend (BFF) Proxy** pattern between a **Next.js 16 / React 19** frontend and a **Django REST Framework + SimpleJWT** backend.
>
> When you finish, the frontend stores tokens in **HttpOnly cookies** managed by Next.js Route Handlers. The browser never sees a raw JWT. Django stays the sole identity authority — no third-party auth library (Auth.js/NextAuth) sits between them.

### Who this is for & how to use it

- **Audience:** interns and engineers wiring up the web client for the first time.
- **Stack this targets (verified against this repo):**
  - Frontend: `next@16.2.6`, `react@19.2`, `vitest@4`, `tailwindcss@4`, path alias `@/* → frontend/` (see `jsconfig.json`).
  - Backend: Django + DRF + `djangorestframework-simplejwt` with endpoints under `/api/v1/accounts/`.
- **How to use:** Work through Section 4 **in order**. Every step ships real code and a `Verify` checkpoint. Do not skip ahead — each step builds on the previous one.
- **Golden rule:** the browser talks **only** to Next.js (`/api/...`). Next.js talks to Django. Tokens live in HttpOnly cookies and never touch JavaScript.

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
┌───────────────────────────────────────────────────────────────────┐
│                    Next.js BFF Layer                              │
│                                                                   │
│   ┌─────────────────────────────────────────────────────────┐     │
│   │  middleware.js (or proxy.js in Next.js 16)              │     │
│   │  • Checks if access_token OR refresh_token cookie exists│     │
│   │  • Redirects to /login if neither present               │     │
│   │  • Does NOT validate token (that's the route handler)   │     │
│   └──────────────────────────┬──────────────────────────────┘     │
│                              │                                    │
│   ┌──────────────────────────▼──────────────────────────────┐     │
│   │  Route Handlers (app/api/)                              │     │
│   │                                                         │     │
│   │  /api/auth/login   → POST /accounts/auth/login/         │     │
│   │                      Set httpOnly cookies               │     │
│   │                                                         │     │
│   │  /api/auth/refresh → POST /accounts/auth/refresh/       │     │
│   │                      Rotate + update cookies            │     │
│   │                                                         │     │
│   │  /api/auth/logout  → POST /accounts/auth/logout/        │     │
│   │                      Clear cookies                      │     │
│   │                                                         │     │
│   │  /api/proxy/[...path] → Read access_token cookie        │     │
│   │                          Inject Authorization header    │     │
│   │                          Forward to Django              │     │
│   └──────────────────────────┬──────────────────────────────┘     │
│                              │                                    │
│   ┌──────────────────────────▼──────────────────────────────┐     │
│   │  Server Components                                      │     │
│   │  • Read cookies via cookies()                           │     │
│   │  • Call lib/api.js which uses the proxy                 │     │
│   │  • Or call Django directly with the token               │     │
│   └─────────────────────────────────────────────────────────┘     │
│                                                                   │
└──────────────────────────┬────────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────────────┐
│                     Django Backend (unchanged)                     │
│                                                                    │
│   POST /api/v1/accounts/auth/login/    → { data: { tokens, user } }│
│   POST /api/v1/accounts/auth/refresh/  → { access, refresh }       │
│   POST /api/v1/accounts/auth/logout/   → 200 (blacklists refresh)  │
│   POST /api/v1/accounts/auth/register/ → { user, tokens }          │
│   GET  /api/v1/accounts/users/me/      → current user              │
│   GET  /api/v1/*                       → resource APIs             │
│   WS   ws/chat/{session_id}/?token=…   → WebSocket consumers       │
│                                                                    │
│   Django does not know or care that Next.js is a proxy.            │
│   It sees standard JWT Bearer requests.                            │
└────────────────────────────────────────────────────────────────────┘
```

### Key Principle

The browser **never talks to Django directly**. Every authenticated request goes through the Next.js BFF layer. The browser only sees:
- `httpOnly` cookies it can't read (XSS protection)
- Same-origin requests (no CORS issues)
- Tokens it never sees in JavaScript

The Django API remains **unified** — the React Native mobile app talks to the same endpoints directly using tokens in secure storage (iOS Keychain / Android Keystore).

---

## 2. Prerequisites

- Backend running on `http://localhost:8000` with DRF + SimpleJWT.
- `next-auth` is **not** installed (this repo never added it — keep it that way).
- Node 20+, and `npm install` already run in `frontend/`.

### 2.1 Backend endpoint contract (verified against this repo)

These are the **actual** endpoints your Route Handlers will call. The base path is
`/api/v1` and all auth lives under `/accounts/`. Do not invent `/auth/token/` paths —
they don't exist here.

| Purpose | Method & Path | Request body | Success response (relevant fields) |
|---|---|---|---|
| **Login** | `POST /api/v1/accounts/auth/login/` | `{ "email", "password" }` | `{ "data": { "tokens": { "access", "refresh" }, "user": {…}, "navigation": { "dashboard_route" } } }` |
| **Refresh** | `POST /api/v1/accounts/auth/refresh/` | `{ "refresh" }` | `{ "access", "refresh" }` (new `refresh` because rotation is on) |
| **Logout** | `POST /api/v1/accounts/auth/logout/` | `{ "refresh" }` | `200` (refresh token invalidated) |
| **Register** | `POST /api/v1/accounts/auth/register/` | `{ "email", "password1", "password2", "first_name", "last_name" }` | `{ "user": {…}, "tokens": { "access", "refresh" } }` |
| **Current user** | `GET /api/v1/accounts/users/me/` | — (Bearer) | `{ "id", "email", "first_name", "last_name", "full_name", "role", … }` |

> **Login field is `email`, not `username`.** The custom `TokenObtainPairSerializer`
> sets `username_field = User.EMAIL_FIELD`.

**SimpleJWT settings you must mirror in `lib/cookies.js`:**

| Setting | Value | Why it matters to you |
|---|---|---|
| `ACCESS_TOKEN_LIFETIME` | `5 minutes` | Access cookie `max-age = 300`. |
| `REFRESH_TOKEN_LIFETIME` | `1 day` | Refresh cookie `max-age = 86400`. |
| `ROTATE_REFRESH_TOKENS` | `True` | **Refresh returns a new refresh token** — you must overwrite the refresh cookie on every refresh. |
| `BLACKLIST_AFTER_ROTATION` | `False` | The old refresh token is not instantly killed, which softens the classic race. Your process lock still prevents redundant calls. |
| `AUTH_HEADER_TYPES` | `("Bearer",)` | Proxy injects `Authorization: Bearer <access>`. |

> ℹ️ Django also sets its **own** `httpOnly` cookies on login. We ignore those — they
> are set on the *server-to-server* fetch and never reach the browser. We read the
> tokens out of the **JSON body** and set our **own** cookies under Next.js control.

### 2.1.1 Error response contract

Django auth endpoints return a **custom error envelope**, not DRF's default `{ "detail": "…" }`.
Your route handlers must handle both shapes. The canonical error shape is:

```json
{
  "message": "Human-readable error",
  "code": "machine_code",
  "status": "error",
  "errors": { "field": ["…"] }   // optional — field-level validation errors
}
```

| Scenario | HTTP | `code` | Notes |
|---|---|---|---|
| Missing email/password | 400 | `required_fields_missing` | |
| Bad credentials | 401 | `authentication_failed` / `invalid_credentials` | Same message for "no user" and "wrong password" (no enumeration) |
| Inactive account | 403 | `account_inactive` | |
| Validation error (register) | 400 | `validation_error` | `errors` dict has per-field messages |
| Email already exists | 400 | `email_already_exists` | |
| Throttled | 429 | — | DRF returns `{"detail": "Request was throttled…"}` |
| Expired/invalid refresh | 401 | — | SimpleJWT returns `{"detail": "Token is invalid or expired"}` |

> **In your route handlers**, always read errors defensively:
> `payload?.message || payload?.detail || "Generic error"`. This covers both the custom
> envelope and SimpleJWT's raw `detail` shape.

### 2.2 Environment Variables

`frontend/.env.local` (already present in this repo):

| Variable | Example | Purpose |
|----------|---------|---------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000/api/v1` | Public base used by client code (e.g. building WS URLs). Exposed to the browser. |
| `INTERNAL_API_URL` | `http://localhost:8000/api/v1` | Server-side base used by Route Handlers. Same in dev; in Docker/prod this becomes the internal service name (e.g. `http://backend:8000/api/v1`). |
| `NEXT_PUBLIC_BASE_URL` | `http://localhost:8000` | Origin for non-API assets. |
| `NEXT_PUBLIC_WS_HOST` | `localhost:8000` | WebSocket host (no scheme). |

> ⚠️ **No `AUTH_SECRET` / `AUTH_TRUST_HOST` needed.** We are not encrypting cookies with
> a framework secret — Django already signs the JWTs. Keep the env surface minimal.

Document every new env var in `frontend/.env.example` (already mirrored there).

---

## 3. Files You Will Create

```
frontend/
├── middleware.js                            # Route protection (checks cookie existence)
├── app/
│   ├── api/
│   │   └── auth/
│   │       ├── login/route.js               # Login proxy → Django
│   │       ├── refresh/route.js             # Refresh proxy → Django (with lock + rotation)
│   │       ├── logout/route.js              # Logout proxy → Django blacklist
│   │       ├── register/route.js            # Registration proxy → Django
│   │       ├── me/route.js                  # Current user proxy → Django
│   │       ├── ws-token/route.js            # Short-lived access token for WebSocket auth
│   │       └── social/google/route.js       # Google OAuth proxy → Django (Section 9 BE doc)
│   ├── api/proxy/[...path]/route.js          # Generic catch-all API proxy
│   ├── login/page.jsx                        # Login form (calls /api/auth/login)
│   └── (app)/                                # Authenticated route group
│       ├── layout.jsx                        # Server component: validates session
│       ├── chat/page.jsx
│       └── settings/page.jsx
├── lib/
│   ├── django.js                            # Django base URL + endpoint paths (one source of truth)
│   ├── cookies.js                           # Cookie names, options, set/clear helpers
│   ├── jwt.js                               # Decode JWT `exp` (no verify) to detect expiry
│   ├── refresh.js                           # Per-token in-flight lock (collapses concurrent refreshes)
│   ├── server-auth.js                       # getValidAccessToken(): refresh-on-demand for server code
│   ├── api.js                               # Server-side fetch helper (reads cookies, auto-refresh)
│   ├── api-client.js                        # Client-side fetch helper (calls the proxy)
│   └── ws.js                                # WebSocket connection helper
└── __tests__/
    ├── auth/
    │   ├── login.test.js
    │   ├── refresh.test.js                  # includes the concurrency-lock test
    │   ├── logout.test.js
    │   └── proxy.test.js
    └── middleware.test.js
```

---

## 4. Step-by-Step Implementation Plan

Work in this order. Do not skip ahead. Each step ends with a verifiable outcome.

### Step 1 — Foundation modules (`lib/django.js`, `lib/cookies.js`, `lib/jwt.js`)

Three tiny, dependency-free modules everything else builds on. Define them once; never hardcode a path or cookie name anywhere else.

#### `lib/django.js` — one source of truth for Django

```js
// lib/django.js
// The ONLY place Django URLs are defined. Route Handlers import from here.

// Server-side base (Docker/prod may differ from the browser base).
export const DJANGO_API = process.env.INTERNAL_API_URL ?? "http://localhost:8000/api/v1";

export const ENDPOINTS = {
  login: "/accounts/auth/login/",
  refresh: "/accounts/auth/refresh/",
  logout: "/accounts/auth/logout/",
  register: "/accounts/auth/register/",
  me: "/accounts/users/me/",
};

/** Build an absolute Django URL from a relative API path. */
export function djangoUrl(path) {
  const clean = path.startsWith("/") ? path : `/${path}`;
  return `${DJANGO_API}${clean}`;
}
```

#### `lib/cookies.js` — cookie names, options, and set/clear helpers

```js
// lib/cookies.js
// The ONLY place cookie names + options are defined.

export const ACCESS_TOKEN_COOKIE = "access_token";
export const REFRESH_TOKEN_COOKIE = "refresh_token";

// Mirror Django SIMPLE_JWT:
//   ACCESS_TOKEN_LIFETIME  = timedelta(minutes=5)
//   REFRESH_TOKEN_LIFETIME = timedelta(days=1)
export const ACCESS_MAX_AGE = 5 * 60; // 300s
export const REFRESH_MAX_AGE = 24 * 60 * 60; // 86400s

const isProd = process.env.NODE_ENV === "production";

/** Base options shared by both cookies. */
function baseOptions() {
  return {
    httpOnly: true, // JavaScript can never read these → XSS-safe
    secure: isProd, // HTTPS-only in production
    sameSite: "lax", // matches Django; "strict" can break OAuth-style redirects
    path: "/",
  };
}

/**
 * Write both auth cookies onto a resolved cookie store.
 * In Next.js 16 `cookies()` is async — pass the awaited store.
 */
export function setAuthCookies(cookieStore, { access, refresh }) {
  if (access) {
    cookieStore.set(ACCESS_TOKEN_COOKIE, access, {
      ...baseOptions(),
      maxAge: ACCESS_MAX_AGE,
    });
  }
  if (refresh) {
    cookieStore.set(REFRESH_TOKEN_COOKIE, refresh, {
      ...baseOptions(),
      maxAge: REFRESH_MAX_AGE,
    });
  }
}

/** Remove both auth cookies (logout / failed refresh). */
export function clearAuthCookies(cookieStore) {
  cookieStore.set(ACCESS_TOKEN_COOKIE, "", { ...baseOptions(), maxAge: 0 });
  cookieStore.set(REFRESH_TOKEN_COOKIE, "", { ...baseOptions(), maxAge: 0 });
}
```

#### `lib/jwt.js` — read the `exp` claim without verifying

We never *verify* the JWT in Next.js (Django does that). We only decode `exp` so the proxy can refresh **proactively** instead of waiting for a `401`.

```js
// lib/jwt.js
/** Decode a JWT payload without verifying the signature. Returns null on garbage. */
export function decodeJwt(token) {
  try {
    const [, payload] = token.split(".");
    const json = Buffer.from(payload, "base64url").toString("utf8");
    return JSON.parse(json);
  } catch {
    return null;
  }
}

/** True if the token is missing, malformed, or expires within `skewSeconds`. */
export function isExpired(token, skewSeconds = 10) {
  const payload = decodeJwt(token);
  if (!payload?.exp) return true;
  const now = Math.floor(Date.now() / 1000);
  return payload.exp <= now + skewSeconds;
}
```

**Verify:** `npm run build` passes and importing these from a route handler resolves with the `@/lib/...` alias.

---

### Step 2 — Login Route Handler (`app/api/auth/login/route.js`)

The BFF login endpoint. The browser POSTs `{ email, password }` here. The handler:
1. Validates input.
2. Calls Django `/accounts/auth/login/`.
3. Reads `data.tokens.access` / `data.tokens.refresh` from the **JSON body**.
4. Sets both as `httpOnly` cookies.
5. Returns **only** the user object + navigation hint. **No tokens in the body.**

```js
// app/api/auth/login/route.js
import { cookies } from "next/headers";
import { djangoUrl, ENDPOINTS } from "@/lib/django";
import { setAuthCookies } from "@/lib/cookies";

export async function POST(request) {
  let body;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const { email, password } = body ?? {};
  if (!email || !password) {
    return Response.json({ error: "Email and password are required" }, { status: 400 });
  }

  // Call Django. Never forward the browser's cookies here.
  const djangoRes = await fetch(djangoUrl(ENDPOINTS.login), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
    cache: "no-store",
  });

  const payload = await djangoRes.json().catch(() => ({}));

  if (!djangoRes.ok) {
    // Surface Django's error but never its internals/stack.
    const message = payload?.message || payload?.detail || "Invalid credentials";
    return Response.json({ error: message }, { status: djangoRes.status });
  }

  // Response is wrapped: { data: { tokens: { access, refresh }, user, navigation } }
  const tokens = payload?.data?.tokens ?? payload?.tokens;
  const user = payload?.data?.user ?? payload?.user;
  const navigation = payload?.data?.navigation ?? null;

  if (!tokens?.access || !tokens?.refresh) {
    return Response.json({ error: "Malformed token response from server" }, { status: 502 });
  }

  const cookieStore = await cookies();
  setAuthCookies(cookieStore, tokens);

  // Body carries NO tokens — only safe profile data.
  return Response.json({ user, navigation }, { status: 200 });
}
```

> **Why no tokens in the body?** If the client can read the token, so can an XSS payload.
> The whole point of the BFF is that JavaScript never sees the JWT.

**Verify:**
```bash
curl -i -X POST http://localhost:3000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@aparsoft.com","password":"test123"}'
```
The response sets `access_token` and `refresh_token` cookies (look for `Set-Cookie` with `HttpOnly`) and the JSON body contains `user` but **not** `access`/`refresh`.

#### Optional — Registration (`app/api/auth/register/route.js`)

Same shape as login, but Django expects `password1`/`password2` and returns
`{ user, tokens }` (flat, not under `data`). Auto-login the new user by setting cookies.

```js
// app/api/auth/register/route.js
import { cookies } from "next/headers";
import { djangoUrl, ENDPOINTS } from "@/lib/django";
import { setAuthCookies } from "@/lib/cookies";

export async function POST(request) {
  const body = await request.json().catch(() => null);
  if (!body?.email || !body?.password1 || body.password1 !== body.password2) {
    return Response.json({ error: "Invalid registration data" }, { status: 400 });
  }

  const res = await fetch(djangoUrl(ENDPOINTS.register), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  const payload = await res.json().catch(() => ({}));

  if (!res.ok) {
    return Response.json({ error: payload?.message || "Registration failed", fields: payload }, { status: res.status });
  }

  const tokens = payload?.tokens ?? payload?.data?.tokens;
  if (tokens?.access && tokens?.refresh) {
    const cookieStore = await cookies();
    setAuthCookies(cookieStore, tokens); // auto-login
  }
  return Response.json({ user: payload?.user ?? payload?.data?.user }, { status: 201 });
}
```

#### Optional — Google OAuth (`app/api/auth/social/google/route.js`)

Pairs with the backend `GoogleLoginView` (see [backend AUTHENTICATION.md §9](../../backend/docs/AUTHENTICATION.md#9-google-oauth-gold-standard-implementation)).
The browser obtains a Google **ID token** via Google Identity Services, sends it here,
and the BFF forwards it to Django. Django verifies the token and returns our JWT pair —
the BFF sets cookies exactly like password login.

```js
// app/api/auth/social/google/route.js
import { cookies } from "next/headers";
import { setAuthCookies } from "@/lib/cookies";

const DJANGO_API = process.env.INTERNAL_API_URL ?? "http://localhost:8000/api/v1";

export async function POST(request) {
  const { id_token } = await request.json().catch(() => ({}));
  if (!id_token) {
    return Response.json({ error: "Google ID token is required" }, { status: 400 });
  }

  const res = await fetch(`${DJANGO_API}/accounts/auth/social/google/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_token }),
    cache: "no-store",
  });

  const payload = await res.json().catch(() => ({}));
  if (!res.ok) {
    return Response.json(
      { error: payload?.message || "Google authentication failed" },
      { status: res.status },
    );
  }

  // Django returns the same wrapped shape as password login.
  const tokens = payload?.data?.tokens ?? payload?.tokens;
  const user = payload?.data?.user ?? payload?.user;
  if (!tokens?.access || !tokens?.refresh) {
    return Response.json({ error: "Malformed token response" }, { status: 502 });
  }

  const cookieStore = await cookies();
  setAuthCookies(cookieStore, tokens); // same cookies as password login
  return Response.json({ user }, { status: 200 });
}
```

The browser-side Google Sign-In button (using `@react-oauth/google` or the
`google.accounts.id` script) calls this route with the `credential` (ID token) it receives
from Google. No `client_secret` ever touches the browser.

---

### Step 3 — Refresh logic + Route Handler

The most important piece. Two requirements:

1. **Rotation:** because `ROTATE_REFRESH_TOKENS=True`, Django returns a **new** refresh
   token. You must overwrite **both** cookies, not just the access cookie.
2. **Concurrency collapsing:** if several requests trigger a refresh at the same
   millisecond, only **one** call should hit Django; the rest await the same result.

Put the lock in a **shared module** so the refresh route, the proxy, and `lib/api.js`
all use the *same* in-flight promise (a Node module is a singleton per process).

#### `lib/refresh.js` — per-token in-flight collapsing

```js
// lib/refresh.js
import { djangoUrl, ENDPOINTS } from "@/lib/django";

// Key the lock by the refresh-token value so DIFFERENT users never share a promise.
// (A single global promise would hand user B's tokens to user A.)
const inFlight = new Map();

async function callDjangoRefresh(refreshToken) {
  const res = await fetch(djangoUrl(ENDPOINTS.refresh), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh: refreshToken }),
    cache: "no-store",
  });

  if (!res.ok) {
    const err = new Error("Token refresh failed");
    err.status = res.status; // 401 → refresh token is dead
    throw err;
  }

  const data = await res.json().catch(() => ({}));
  // Tolerate both flat SimpleJWT shape and a wrapped { data: { tokens } } shape.
  const tokens = data?.data?.tokens ?? data;
  return {
    access: tokens.access,
    refresh: tokens.refresh ?? refreshToken, // keep old if backend didn't rotate
  };
}

/**
 * Refresh tokens, collapsing concurrent callers that share the same refresh token
 * onto a single Django request. Returns { access, refresh }. Throws on failure.
 */
export function refreshTokens(refreshToken) {
  if (inFlight.has(refreshToken)) return inFlight.get(refreshToken);
  const promise = callDjangoRefresh(refreshToken).finally(() =>
    inFlight.delete(refreshToken),
  );
  inFlight.set(refreshToken, promise);
  return promise;
}
```

#### `app/api/auth/refresh/route.js`

```js
// app/api/auth/refresh/route.js
import { cookies } from "next/headers";
import { REFRESH_TOKEN_COOKIE, setAuthCookies, clearAuthCookies } from "@/lib/cookies";
import { refreshTokens } from "@/lib/refresh";

export async function POST() {
  const cookieStore = await cookies();
  const refreshToken = cookieStore.get(REFRESH_TOKEN_COOKIE)?.value;

  if (!refreshToken) {
    return Response.json({ error: "No refresh token" }, { status: 401 });
  }

  try {
    const tokens = await refreshTokens(refreshToken);
    setAuthCookies(cookieStore, tokens); // rotation: writes BOTH cookies
    return Response.json({ ok: true }, { status: 200 });
  } catch (err) {
    // Refresh token expired/blacklisted → force re-login.
    clearAuthCookies(cookieStore);
    return Response.json({ error: "Session expired" }, { status: 401 });
  }
}
```

> ⚠️ **Process-scoped lock.** This collapses concurrency within **one** Node process —
> perfect for single-server / Docker. On multi-instance serverless you'd need a
> distributed lock (Redis). With `BLACKLIST_AFTER_ROTATION=False` (this repo's setting),
> a stray second call is harmless anyway because the old refresh token is not killed.

**Verify:** Expire the access cookie in DevTools, then load a page with 3 parallel Server
Components. All succeed; your Django logs show **one** refresh call, not three.

---

### Step 4 — Logout Route Handler (`app/api/auth/logout/route.js`)

Blacklist the refresh token on Django, then clear cookies **regardless** of whether the
Django call succeeds (a network blip must not trap the user in a logged-in shell).

```js
// app/api/auth/logout/route.js
import { cookies } from "next/headers";
import { djangoUrl, ENDPOINTS } from "@/lib/django";
import { REFRESH_TOKEN_COOKIE, clearAuthCookies } from "@/lib/cookies";

export async function POST() {
  const cookieStore = await cookies();
  const refresh = cookieStore.get(REFRESH_TOKEN_COOKIE)?.value;

  if (refresh) {
    try {
      await fetch(djangoUrl(ENDPOINTS.logout), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh }),
        cache: "no-store",
      });
    } catch {
      // Network error — still clear local cookies below.
    }
  }

  clearAuthCookies(cookieStore);
  return Response.json({ ok: true }, { status: 200 });
}
```

**Verify:** After hitting logout, both cookies are gone (DevTools → Application → Cookies)
and the refresh token no longer works against Django's refresh endpoint.

---

### Step 5 — Session helper + Current User Route

First, a small server-only helper that **guarantees a valid access token**, refreshing
proactively when needed. The `me` route, the proxy, and `lib/api.js` all reuse it.

#### `lib/server-auth.js`

```js
// lib/server-auth.js  (server-only — reads/writes cookies)
import {
  ACCESS_TOKEN_COOKIE,
  REFRESH_TOKEN_COOKIE,
  setAuthCookies,
  clearAuthCookies,
} from "@/lib/cookies";
import { isExpired } from "@/lib/jwt";
import { refreshTokens } from "@/lib/refresh";

/**
 * Return a usable access token, refreshing if the current one is expired.
 * Rotated cookies are written as a side effect. Returns null if the session is dead.
 * `cookieStore` must be the awaited result of cookies().
 */
export async function getValidAccessToken(cookieStore) {
  const access = cookieStore.get(ACCESS_TOKEN_COOKIE)?.value;
  if (access && !isExpired(access)) return access;

  const refresh = cookieStore.get(REFRESH_TOKEN_COOKIE)?.value;
  if (!refresh) return null;

  try {
    const tokens = await refreshTokens(refresh);
    setAuthCookies(cookieStore, tokens);
    return tokens.access;
  } catch {
    clearAuthCookies(cookieStore);
    return null;
  }
}
```

#### `app/api/auth/me/route.js`

```js
// app/api/auth/me/route.js
import { cookies } from "next/headers";
import { djangoUrl, ENDPOINTS } from "@/lib/django";
import { getValidAccessToken } from "@/lib/server-auth";

export async function GET() {
  const cookieStore = await cookies();
  const access = await getValidAccessToken(cookieStore);
  if (!access) return Response.json({ error: "Not authenticated" }, { status: 401 });

  const res = await fetch(djangoUrl(ENDPOINTS.me), {
    headers: { Authorization: `Bearer ${access}` },
    cache: "no-store",
  });

  if (!res.ok) return Response.json({ error: "Failed to load user" }, { status: res.status });

  const user = await res.json();
  return Response.json({ user }, { status: 200 });
}
```

Client components call `/api/auth/me` to check auth status without ever touching a token.

**Verify:** With a logged-in browser, `fetch('/api/auth/me').then(r => r.json())` returns
the user. With no cookies, it returns `401`.

---

### Step 6 — Generic API Proxy (`app/api/proxy/[...path]/route.js`)

The **catch-all** that forwards any client request to Django with a valid token injected.
Client components never touch tokens — they just `fetch('/api/proxy/...')`.

```js
// app/api/proxy/[...path]/route.js
import { cookies } from "next/headers";
import { djangoUrl } from "@/lib/django";
import { getValidAccessToken } from "@/lib/server-auth";

const BODY_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

async function handler(request, ctx) {
  const { path = [] } = await ctx.params; // Next.js 16: params is async
  const cookieStore = await cookies();

  const access = await getValidAccessToken(cookieStore);
  if (!access) return Response.json({ error: "Not authenticated" }, { status: 401 });

  // /api/proxy/chat/sessions/?x=1  →  <DJANGO>/chat/sessions/?x=1
  const search = new URL(request.url).search;
  const target = djangoUrl(`/${path.join("/")}/`) + search;

  const init = {
    method: request.method,
    headers: { Authorization: `Bearer ${access}` },
    cache: "no-store",
  };

  const contentType = request.headers.get("content-type");
  if (BODY_METHODS.has(request.method)) {
    if (contentType) init.headers["Content-Type"] = contentType;
    init.body = await request.text(); // pass the raw body straight through
  }

  const djangoRes = await fetch(target, init);

  // Stream Django's response back unchanged.
  const body = await djangoRes.arrayBuffer();
  return new Response(body, {
    status: djangoRes.status,
    headers: {
      "Content-Type": djangoRes.headers.get("content-type") ?? "application/json",
    },
  });
}

export {
  handler as GET,
  handler as POST,
  handler as PUT,
  handler as PATCH,
  handler as DELETE,
};
```

Now a client component is trivial — no token handling at all:

```js
// Client component
const res = await fetch("/api/proxy/chat/sessions/");
const sessions = await res.json();
```

> **Note on trailing slashes.** DRF routers expect a trailing slash (`APPEND_SLASH`).
> The proxy adds one after `path.join("/")`. If a specific endpoint must omit it, special-case that route.

**Verify:** From a logged-in browser,
`fetch('/api/proxy/accounts/users/me/').then(r => r.json())` returns user data.

---

### Step 7 — Middleware (`middleware.js`)

Create `middleware.js` at the project root. This is the **first line of defense** — a bouncer that checks if you have a ticket.

1. Check if a session cookie exists (`access_token` **or** `refresh_token`).
2. If neither is present, redirect to `/login`.
3. Otherwise, let the request through (the server layer validates the token).

> ⚠️ **Middleware does NOT validate the token.** It only checks cookie existence. Token validation happens server-side in the route handlers and layouts. Think of middleware as a bouncer checking if you have a ticket, while your server components verify the ticket is valid.

```js
// middleware.js
import { NextResponse } from "next/server";
import { ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE } from "@/lib/cookies";

export function middleware(request) {
  // A session "exists" if either cookie is present. The access cookie may have
  // expired (max-age 5m) while the refresh cookie is still valid — don't kick the
  // user out in that case; the proxy/layout will refresh server-side.
  const hasSession =
    request.cookies.get(ACCESS_TOKEN_COOKIE) || request.cookies.get(REFRESH_TOKEN_COOKIE);

  if (!hasSession) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("callbackUrl", request.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  // Run on everything EXCEPT public pages, ALL /api routes (they handle their own
  // auth and must return JSON, not an HTML redirect), and static assets.
  matcher: [
    "/((?!login|register|api|_next/static|_next/image|favicon.ico|public).*)",
  ],
};
```

> Why match on **either** cookie? The access cookie lives 5 minutes; the refresh cookie
> lives a day. If middleware required the access cookie, users would bounce to `/login`
> every 5 minutes even though their session is still refreshable.

**Note on Next.js 16 `proxy.js`:** Next.js 16 ships `proxy.js` as the eventual successor to `middleware.js`. The patterns here port over 1:1; migrating is a mechanical follow-up (see Section 8). Stick with `middleware.js` for now — it has the most examples.

**Verify:** Visit `http://localhost:3000/chat` without being logged in. You should be redirected to `/login?callbackUrl=/chat`.

---

### Step 8 — Login Page + Client Helper

#### `app/login/page.jsx`

A client component. It POSTs to the BFF, then lets the server set cookies. **Zero**
token handling, **zero** `localStorage`.

```jsx
// app/login/page.jsx
"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const callbackUrl = params.get("callbackUrl") || "/chat";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Login failed");
        return;
      }
      // Prefer Django's navigation hint, else the callback URL.
      const dest = data?.navigation?.dashboard_route || callbackUrl;
      router.replace(dest);
      router.refresh(); // re-run server components now that cookies exist
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="mx-auto mt-24 flex w-80 flex-col gap-3">
      <h1 className="text-xl font-semibold">Sign in</h1>
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
      <input
        type="email" required autoComplete="email"
        placeholder="you@example.com"
        value={email} onChange={(e) => setEmail(e.target.value)}
        className="rounded border p-2"
      />
      <input
        type="password" required autoComplete="current-password"
        placeholder="Password"
        value={password} onChange={(e) => setPassword(e.target.value)}
        className="rounded border p-2"
      />
      <button type="submit" disabled={loading}
        className="rounded bg-black p-2 text-white disabled:opacity-50">
        {loading ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}

export default function LoginPage() {
  // useSearchParams() must sit inside a Suspense boundary in the App Router.
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
```

#### `lib/api-client.js` — client-side fetch through the proxy

```js
// lib/api-client.js  (used by "use client" components)
// Thin wrapper over the BFF proxy. Redirects to /login on 401.

export async function apiClient(path, options = {}) {
  const res = await fetch(`/api/proxy/${path.replace(/^\//, "")}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });

  if (res.status === 401 && typeof window !== "undefined") {
    window.location.href = "/login";
    return null;
  }
  return res;
}
```

**Verify:** Log in. DevTools → Application → Cookies shows `access_token` and
`refresh_token` flagged `HttpOnly`. DevTools → Local Storage is **empty**. You land on
the dashboard/callback URL.

---

### Step 9 — Server-Side API Helper (`lib/api.js`)

For **Server Components** and **Server Actions**. They run on the server, so they call
Django directly (no proxy hop) with auth handled by `getValidAccessToken`.

```js
// lib/api.js  (server-only)
import { cookies } from "next/headers";
import { djangoUrl } from "@/lib/django";
import { getValidAccessToken } from "@/lib/server-auth";

/**
 * Fetch a Django API path from the server with auth handled.
 * Returns parsed JSON. Throws (with `.status`) on non-OK so callers can
 * try/catch or let it bubble to the nearest error.js boundary.
 */
export async function apiFetch(path, options = {}) {
  const cookieStore = await cookies();
  const access = await getValidAccessToken(cookieStore);
  if (!access) {
    const err = new Error("UNAUTHENTICATED");
    err.status = 401;
    throw err;
  }

  const res = await fetch(djangoUrl(path), {
    ...options,
    headers: {
      Authorization: `Bearer ${access}`,
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    cache: "no-store",
  });

  if (!res.ok) {
    const err = new Error(`API ${res.status} for ${path}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}
```

```jsx
// Usage in a Server Component:
import { apiFetch } from "@/lib/api";

export default async function ChatPage() {
  const sessions = await apiFetch("/chat/sessions/");
  return <SessionList sessions={sessions} />;
}
```

---

### Step 10 — Authenticated Route Group (`app/(app)/`)

A server-component `layout.jsx` that validates the session before any protected page renders.

#### `app/(app)/layout.jsx`

```jsx
// app/(app)/layout.jsx  (Server Component)
import { redirect } from "next/navigation";
import { cookies } from "next/headers";
import { djangoUrl, ENDPOINTS } from "@/lib/django";
import { getValidAccessToken } from "@/lib/server-auth";
import LogoutButton from "./LogoutButton";

export default async function AppLayout({ children }) {
  const cookieStore = await cookies();
  const access = await getValidAccessToken(cookieStore);
  if (!access) redirect("/login");

  // Validate by loading the user. If Django rejects the token, bounce to login.
  const res = await fetch(djangoUrl(ENDPOINTS.me), {
    headers: { Authorization: `Bearer ${access}` },
    cache: "no-store",
  });
  if (!res.ok) redirect("/login");
  const user = await res.json();

  return (
    <div className="flex min-h-screen">
      <aside className="w-60 border-r p-4">{/* nav links */}</aside>
      <div className="flex-1">
        <header className="flex items-center justify-between border-b p-4">
          <span>{user.full_name || user.email}</span>
          <LogoutButton />
        </header>
        <main className="p-4">{children}</main>
      </div>
    </div>
  );
}
```

#### `app/(app)/LogoutButton.jsx`

```jsx
// app/(app)/LogoutButton.jsx
"use client";

import { useRouter } from "next/navigation";

export default function LogoutButton() {
  const router = useRouter();
  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.replace("/login");
    router.refresh();
  }
  return (
    <button onClick={logout} className="text-sm underline">
      Sign out
    </button>
  );
}
```

This is the **second line of defense** (belt-and-braces after middleware):
- **Middleware:** Fast cookie-existence check (runs at the edge, every request)
- **Layout:** Full token validation (runs server-side, page loads only)

**Verify:** Logged-in users see the app. Logged-out users get redirected by middleware BEFORE the page renders (no flash of protected content).

---

### Step 11 — WebSocket Authentication

**Current backend contract (verified):** the chat consumer authenticates by reading a JWT
from the **query string** — `ws/chat/{session_id}/?token=<access>` (see
`backend/apps/chatbot/consumers/chat_consumer.py`). Browsers cannot read the `httpOnly`
cookie, so the client must obtain a fresh access token from the BFF first.

#### `app/api/auth/ws-token/route.js` — hand the client a short-lived token

```js
// app/api/auth/ws-token/route.js
import { cookies } from "next/headers";
import { getValidAccessToken } from "@/lib/server-auth";

export async function GET() {
  const cookieStore = await cookies();
  const token = await getValidAccessToken(cookieStore); // refreshes if needed
  if (!token) return Response.json({ error: "Not authenticated" }, { status: 401 });
  return Response.json({ token }, { status: 200 });
}
```

#### `lib/ws.js` — open the authenticated socket

```js
// lib/ws.js  (client)
export async function openChatSocket(sessionId, { onMessage, onError } = {}) {
  const res = await fetch("/api/auth/ws-token");
  if (!res.ok) throw new Error("Not authenticated");
  const { token } = await res.json();

  const host = process.env.NEXT_PUBLIC_WS_HOST; // e.g. localhost:8000
  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${scheme}://${host}/ws/chat/${sessionId}/?token=${token}`);

  if (onMessage) ws.addEventListener("message", (e) => onMessage(JSON.parse(e.data)));
  if (onError) ws.addEventListener("error", onError);
  return ws;
}
```

> ⚠️ **Security trade-off you must understand.** Query-string tokens can be logged by
> reverse proxies, load balancers, and access logs. We mitigate this by handing out only
> a **short-lived (5 min) access token** fetched on demand — never the refresh token.
>
> **Recommended hardening (Phase 2, requires a backend change):** switch the consumer to
> the **auth-frame pattern** — connect with no token in the URL, then send
> `{ "type": "auth", "token": "<access>" }` as the first message; the server validates it
> and keeps or drops the connection. Keep using `/api/auth/ws-token` to source the token.

---

### Step 12 — Tests

Add Vitest tests. Route handlers depend on `next/headers` `cookies()` and `fetch`, so
mock both.

| Test File | What It Tests |
|-----------|--------------|
| `__tests__/auth/login.test.js` | Login: success sets cookies, failure returns error, missing fields rejected, **no tokens in body** |
| `__tests__/auth/refresh.test.js` | Refresh: success rotates both cookies, dead refresh → 401 + cookies cleared, **concurrency lock** (parallel calls → 1 Django request) |
| `__tests__/auth/logout.test.js` | Logout: clears cookies even when Django blacklist fails |
| `__tests__/auth/proxy.test.js` | Proxy: injects `Authorization`, 401 when unauthenticated, forwards body |
| `__tests__/middleware.test.js` | Middleware: redirect without cookies, pass with refresh cookie, public routes skipped |

#### The lock test (the one that proves the race is gone)

```js
// __tests__/auth/refresh.test.js
import { describe, it, expect, vi, beforeEach } from "vitest";
import { refreshTokens } from "@/lib/refresh";

describe("refreshTokens — concurrency collapsing", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("collapses concurrent callers sharing a refresh token into ONE Django call", async () => {
    const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ access: "new-a", refresh: "new-r" }), { status: 200 }),
    );

    // Fire 5 refreshes with the SAME token, simultaneously.
    const results = await Promise.all(
      Array.from({ length: 5 }, () => refreshTokens("same-refresh-token")),
    );

    expect(fetchSpy).toHaveBeenCalledTimes(1); // ← the whole point
    for (const r of results) {
      expect(r).toEqual({ access: "new-a", refresh: "new-r" });
    }
  });

  it("does NOT collapse different users (different refresh tokens)", async () => {
    const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ access: "a", refresh: "r" }), { status: 200 }),
    );

    await Promise.all([refreshTokens("user-a-token"), refreshTokens("user-b-token")]);

    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });
});
```

#### Mocking `next/headers` for route-handler tests

```js
// __tests__/auth/login.test.js
import { describe, it, expect, vi } from "vitest";

const store = new Map();
vi.mock("next/headers", () => ({
  cookies: async () => ({
    get: (k) => (store.has(k) ? { value: store.get(k) } : undefined),
    set: (k, v) => store.set(k, v),
  }),
}));

import { POST } from "@/app/api/auth/login/route";

it("sets cookies and never leaks tokens in the body", async () => {
  vi.spyOn(global, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({ data: { tokens: { access: "a", refresh: "r" }, user: { id: 1 } } }),
      { status: 200 },
    ),
  );

  const req = new Request("http://localhost/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email: "x@y.com", password: "pw" }),
  });
  const res = await POST(req);
  const body = await res.json();

  expect(res.status).toBe(200);
  expect(body.user).toEqual({ id: 1 });
  expect(body.access).toBeUndefined();
  expect(body.refresh).toBeUndefined();
  expect(store.get("access_token")).toBe("a");
});
```

**Verify:** `npm run test` is green, including the lock test.

---

### Step 13 — Documentation Sweep

In the same PR, update:

- `frontend/docs/frontend_guide.md` — auth section points to this BFF playbook
- `frontend/docs/current_status.md` — mark auth as "BFF Proxy pattern (implemented)"
- `frontend/.env.example` — confirm `INTERNAL_API_URL` + `NEXT_PUBLIC_*` are documented; no `AUTH_SECRET`

**Verify:** `next-auth`, `Auth.js`, `useSession`, `signIn`, and `authjs` appear **nowhere** under `frontend/` (this repo never used them — keep it that way).

---

## 5. Architectural Rules This Implementation Locks In

Once the BFF proxy is in place, these become non-negotiable in code review:

1. **No direct token storage.** The frontend never writes to `localStorage` or `sessionStorage` for auth.
2. **No third-party auth library.** Django is the identity authority. Next.js is a proxy. Nothing sits between them.
3. **All authenticated requests go through the proxy.** Client components call `/api/proxy/...`. Server components use `lib/api.js`.
4. **Route protection is two-layer.** Middleware checks cookie existence (fast, edge). Layout/proxy validate the token (server-side, accurate).
5. **Refresh has a per-token lock.** `lib/refresh.js` collapses concurrent refreshes that share a refresh token onto one Django call — keyed by token so different users never share a promise.
6. **Tokens are never persisted in JS.** The only short-lived exposure is the WS token (Step 11); the refresh token never leaves the server.
7. **Django API stays unified.** The same Django endpoints serve both the Next.js web client and the React Native mobile client. No special cookie-auth backend needed.

---

## 6. Pitfalls to Avoid

| Pitfall | The Fix |
|---------|---------|
| **Middleware validates tokens** | Middleware only checks cookie existence. Validation happens in route handlers and layouts. |
| **Refresh race condition** | The per-token in-flight map in `lib/refresh.js` collapses concurrent refreshes for the same token; this repo also sets `BLACKLIST_AFTER_ROTATION=False`, so a stray second call is harmless. |
| **Forgetting refresh-token rotation** | `ROTATE_REFRESH_TOKENS=True` — the refresh response carries a **new** refresh token. Always overwrite **both** cookies, not just the access cookie. |
| **Wrong endpoint paths** | Auth lives under `/api/v1/accounts/auth/...`, not `/api/v1/auth/token/...`. Login is `/accounts/auth/login/` with `{email,password}`. |
| **Reading Django's Set-Cookie** | Django's own auth cookies are set on the server-to-server fetch and never reach the browser. Read tokens from the **JSON body** and set your own cookies. |
| **Cookies not set in production** | Ensure `secure: true` in production and that the cookie domain matches the deployed origin. |
| **Server fetch URL in Docker** | Use `INTERNAL_API_URL` for server-side calls (Docker network), `NEXT_PUBLIC_API_URL` for client-side (browser). |
| **Large cookie payload** | Keep cookies to just the JWT strings. No user objects — fetch user data from `/api/auth/me`. |
| **Stale access token in proxy** | The proxy decodes the JWT `exp` claim (`lib/jwt.js`) and refreshes proactively before forwarding, not after a 401. |
| **Forgetting to clear cookies on logout** | Always clear both cookies, even if the Django blacklist call fails. |
| **`await cookies()`** | In Next.js 16 `cookies()` is **async**. Forgetting `await` yields a thenable with no `.get`. |

---

## 7. How You'll Know You're Done

Tick this list before opening the PR.

- [ ] `npm run build && npm run test` are green.
- [ ] No third-party auth library present. (`grep -ri "next-auth\|authjs\|useSession" frontend/app frontend/lib` returns nothing.)
- [ ] No `localStorage` / `sessionStorage` access for auth. (`grep -rn "localStorage" frontend/app frontend/lib` returns nothing auth-related.)
- [ ] Login sets `httpOnly` cookies. No tokens in response body or JavaScript.
- [ ] Middleware redirects unauthenticated users to `/login?callbackUrl=...`.
- [ ] After 5 minutes idle, a page with multiple Server Components still loads — the per-token lock handled the rotation silently (Django logs show one refresh).
- [ ] Logout clears both cookies and invalidates the refresh token on Django.
- [ ] WebSocket connects via `/api/auth/ws-token` (short-lived token), never the refresh token.
- [ ] All docs updated.

---

## 8. After This PR

Two hardening follow-ups, not required to ship:

1. **WebSocket auth-frame upgrade.** Change the Django consumer to accept the token as the
   first message instead of a query param, then update `lib/ws.js` to send
   `{ type: "auth", token }` on open. Removes the token from URLs/access logs.
2. **Migrate `middleware.js` → `proxy.js`.** Next.js 16 ships a native Proxy API. The
   patterns are identical; the migration is mechanical. Do it once `proxy.js` has more
   community examples.

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

That is the whole playbook. When you have shipped it, the frontend has a production-grade auth architecture that is simple, secure, and maintainable — with no abstraction bloat between Next.js and Django.
