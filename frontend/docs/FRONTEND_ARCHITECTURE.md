# Frontend Architecture Plan — AI Chatbot Platform

> The complete blueprint for building the Next.js 16 frontend that consumes the Django
> backend. Auth is already wired (BFF proxy + TanStack Query hooks). This doc covers
> everything else: route structure, data hooks, components, and build phases.
>
> **Stack:** Next.js 16.2 · React 19.2 · TanStack Query 5 · Tailwind CSS 4 · Vitest 4
> **Auth:** BFF proxy pattern (see [AUTHENTICATION_FRONTEND.md](./AUTHENTICATION_FRONTEND.md))
> **API docs:** [accounts](../../backend/apps/accounts/docs/API_ENDPOINTS.md) · [chatbot](../../backend/apps/chatbot/docs/API_ENDPOINTS.md)

---

## 0. What's Already Built

| Layer | Status | Files |
|-------|--------|-------|
| BFF proxy route handlers | ✅ | `app/api/auth/*`, `app/api/proxy/[...path]/route.js` |
| Auth lib modules | ✅ | `lib/django.js`, `lib/cookies.js`, `lib/jwt.js`, `lib/refresh.js`, `lib/server-auth.js`, `lib/api.js`, `lib/api-client.js` |
| TanStack auth hooks | ✅ | `lib/auth-hooks.js` (`useLogin`, `useLogout`, `useCurrentUser`, `useRegister`, `useGoogleLogin`) |
| Auth pages | ✅ | `app/auth/login/`, `app/auth/register/`, `app/auth/LogoutButton.jsx` |
| Proxy (route guard) | ✅ | `proxy.js` (Next.js 16 — replaces `middleware.js`) |
| Providers | ✅ | `app/providers.js` (QueryClientProvider) |
| UI components | ✅ | `app/components/ui/` (40+ shadcn/ui components) |
| Tests | ✅ | 41 tests (jwt, refresh lock, cookies, django, auth-hooks) |

**What's missing:** Chat UI, dashboard, settings, documents, admin panels, chatbot data hooks.

---

## 1. Route Structure

```
frontend/app/
├── layout.js                          # Root layout (Providers + fonts)
├── page.js                            # Landing → redirect to /chat or /auth/login
├── providers.js                       # QueryClientProvider
│
├── auth/                              # Public (no auth required)
│   ├── login/page.jsx                 # ✅ Done
│   ├── register/page.jsx              # ✅ Done
│   └── LogoutButton.jsx               # ✅ Done
│
├── (app)/                             # Authenticated route group (proxy guards)
│   ├── layout.jsx                     # Server component: validates session, renders sidebar + header
│   │
│   ├── chat/                          # Main chat interface
│   │   ├── page.jsx                   # Chat list + new chat (sidebar of sessions)
│   │   ├── [sessionId]/
│   │   │   └── page.jsx               # Active chat session (messages + input)
│   │   └── components/
│   │       ├── ChatSidebar.jsx        # Session list (search, pin, archive)
│   │       ├── ChatMessage.jsx        # Single message bubble (human/ai)
│   │       ├── ChatInput.jsx          # Message input box (textarea + send)
│   │       ├── ChatStream.jsx         # Streaming message display
│   │       └── SessionActions.jsx     # Archive/pin/delete dropdown
│   │
│   ├── documents/                     # Document management
│   │   ├── page.jsx                   # Document list + upload
│   │   ├── [id]/
│   │   │   └── page.jsx               # Document detail (chunks, status, reprocess)
│   │   └── components/
│   │       ├── DocumentList.jsx       # Table of documents with status badges
│   │       ├── DocumentUpload.jsx     # Drag-and-drop file upload
│   │       └── DocumentStatus.jsx     # Processing status indicator
│   │
│   ├── settings/                      # User settings
│   │   ├── page.jsx                   # Settings hub (tabs)
│   │   ├── profile/
│   │   │   └── page.jsx               # Profile edit (name, email, avatar)
│   │   ├── preferences/
│   │   │   └── page.jsx               # Chat preferences (model, temperature, theme)
│   │   ├── api-keys/
│   │   │   └── page.jsx               # API key management (add, validate, set default)
│   │   ├── tools/
│   │   │   └── page.jsx               # Tool management (activate, configure)
│   │   └── usage/
│   │       └── page.jsx               # Token usage dashboard (charts, limits)
│   │
│   └── admin/                         # Admin-only (role === "admin")
│       ├── page.jsx                   # Admin dashboard (user stats, feedback stats)
│       ├── users/
│       │   └── page.jsx               # User management table
│       ├── prompts/
│       │   └── page.jsx               # System prompt templates (CRUD + rate)
│       └── feedback/
│           └── page.jsx               # Message feedback review queue
│
├── api/                               # BFF route handlers
│   ├── auth/                          # ✅ Done (login, refresh, logout, register, me, ws-token, social/google)
│   └── proxy/[...path]/route.js       # ✅ Done (catch-all proxy)
│
└── components/                        # Shared components
    ├── ui/                            # ✅ Done (40+ shadcn/ui)
    ├── chat/                          # Chat-specific shared components
    │   ├── MarkdownRenderer.jsx       # Render AI markdown responses
    │   ├── MermaidDiagram.jsx         # Render mermaid charts in responses
    │   └── TokenCounter.jsx           # Token usage indicator
    └── layout/
        ├── Sidebar.jsx                # App navigation sidebar
        ├── Header.jsx                 # Top bar (user menu, theme toggle)
        └── ThemeProvider.jsx          # Dark/light mode
```

---

## 2. Data Layer — TanStack Query Hooks

All hooks call the BFF proxy (`/api/proxy/chatbot/...`) via `lib/api-client.js`.
The proxy injects the `Authorization` header from the httpOnly cookie.

### 2.1 Chat sessions (`lib/hooks/chat-sessions.js`)

| Hook | Query/Mutation | Proxy path | Purpose |
|------|---------------|------------|---------|
| `useSessions` | useQuery | `GET /api/proxy/chatbot/chat-sessions/` | List sessions (with filters) |
| `useSession(id)` | useQuery | `GET /api/proxy/chatbot/chat-sessions/{id}/` | Single session detail |
| `useCreateSession` | useMutation | `POST /api/proxy/chatbot/chat-sessions/` | New chat |
| `useUpdateSession` | useMutation | `PATCH /api/proxy/chatbot/chat-sessions/{id}/` | Edit title, etc. |
| `useDeleteSession` | useMutation | `DELETE /api/proxy/chatbot/chat-sessions/{id}/` | Remove |
| `useArchiveSession` | useMutation | `POST /api/proxy/chatbot/chat-sessions/{id}/archive/` | Archive |
| `usePinSession` | useMutation | `POST /api/proxy/chatbot/chat-sessions/{id}/pin/` | Pin/unpin |
| `useSessionStats` | useQuery | `GET /api/proxy/chatbot/chat-sessions/stats/` | Dashboard stats |
| `useSessionAnalytics(id)` | useQuery | `GET /api/proxy/chatbot/chat-sessions/{id}/analytics/` | Per-session analytics |

### 2.2 Chat agent + WebSocket (`lib/hooks/chat-agent.js`)

| Hook | Type | Path | Purpose |
|------|------|------|---------|
| `useChatHistory(sessionId)` | useQuery | `GET /api/proxy/chatbot/chat-agent/history/{sessionId}/` | Load message history |
| `useSendMessage` | useMutation | `POST /api/proxy/chatbot/chat-agent/send/` | Send message (HTTP fallback) |
| `useChatSocket(sessionId)` | custom hook | `ws://host/ws/chat/{sessionId}/?token=...` | Real-time streaming via WebSocket |

**WebSocket flow:** `lib/ws.js` fetches a short-lived token from `/api/auth/ws-token`,
opens `ws://NEXT_PUBLIC_WS_HOST/ws/chat/{sessionId}/?token=<access>`, and listens for
`{ "type": "token", "content": "..." }` (streaming chunks) and `{ "type": "message" }`
(final) and `{ "type": "done" }`.

### 2.3 Documents (`lib/hooks/documents.js`)

| Hook | Type | Path | Purpose |
|------|------|------|---------|
| `useDocuments` | useQuery | `GET /api/proxy/chatbot/documents/` | List (with filters) |
| `useDocument(id)` | useQuery | `GET /api/proxy/chatbot/documents/{id}/` | Detail |
| `useUploadDocument` | useMutation | `POST /api/proxy/chatbot/documents/` | Upload (multipart) |
| `useProcessDocument` | useMutation | `POST /api/proxy/chatbot/documents/{id}/process/` | Trigger processing |
| `useDocumentStatus(id)` | useQuery (poll) | `GET /api/proxy/chatbot/documents/{id}/status/` | Poll processing status |
| `useStorageStats` | useQuery | `GET /api/proxy/chatbot/documents/storage-stats/` | Storage dashboard |

### 2.4 Preferences (`lib/hooks/preferences.js`)

| Hook | Type | Path |
|------|------|------|
| `usePreferences` | useQuery | `GET /api/proxy/chatbot/preferences/me/` |
| `useUpdatePreferences` | useMutation | `PATCH /api/proxy/chatbot/preferences/{id}/` |
| `useSessionConfig` | useQuery | `GET /api/proxy/chatbot/preferences/session-config/` |
| `useResetPreferences` | useMutation | `POST /api/proxy/chatbot/preferences/reset-defaults/` |

### 2.5 Token usage (`lib/hooks/token-usage.js`)

| Hook | Type | Path |
|------|------|------|
| `useUsageStats(days)` | useQuery | `GET /api/proxy/chatbot/token-usage/usage-stats/?days=` |
| `useDailyUsage(date)` | useQuery | `GET /api/proxy/chatbot/token-usage/daily-usage/?date=` |
| `useCheckLimits` | useQuery | `GET /api/proxy/chatbot/token-usage/check-limits/` |
| `useModelBreakdown(days)` | useQuery | `GET /api/proxy/chatbot/token-usage/model-breakdown/?days=` |

### 2.6 API keys (`lib/hooks/api-keys.js`)

| Hook | Type | Path |
|------|------|------|
| `useApiKeys` | useQuery | `GET /api/proxy/chatbot/api-keys/` |
| `useCreateApiKey` | useMutation | `POST /api/proxy/chatbot/api-keys/` |
| `useValidateApiKey` | useMutation | `POST /api/proxy/chatbot/api-keys/{id}/validate/` |
| `useSetDefaultApiKey` | useMutation | `POST /api/proxy/chatbot/api-keys/{id}/set-default/` |
| `useDeactivateApiKey` | useMutation | `POST /api/proxy/chatbot/api-keys/{id}/deactivate/` |
| `useApiKeyProviders` | useQuery | `GET /api/proxy/chatbot/api-keys/providers/` |

### 2.7 Tools (`lib/hooks/tools.js`)

| Hook | Type | Path |
|------|------|------|
| `useTools` | useQuery | `GET /api/proxy/chatbot/tools/` |
| `useToolRegistry` | useQuery | `GET /api/proxy/chatbot/tools/registry/` |
| `useEnabledTools` | useQuery | `GET /api/proxy/chatbot/tools/enabled/` |
| `useActivateTool` | useMutation | `POST /api/proxy/chatbot/tools/{id}/activate/` |
| `useDeactivateTool` | useMutation | `POST /api/proxy/chatbot/tools/{id}/deactivate/` |

### 2.8 Admin hooks (`lib/hooks/admin.js`)

| Hook | Type | Path |
|------|------|------|
| `useUserStats` | useQuery | `GET /api/proxy/accounts/users/stats/` |
| `useFeedbackStats` | useQuery | `GET /api/proxy/chatbot/message-feedback/stats/` |
| `useSystemPrompts` | useQuery | `GET /api/proxy/chatbot/system-prompts/` |
| `useCreatePrompt` | useMutation | `POST /api/proxy/chatbot/system-prompts/` |
| `useRatePrompt` | useMutation | `POST /api/proxy/chatbot/system-prompts/{id}/rate/` |

---

## 3. Query Key Strategy

Centralized query keys for cache invalidation:

```js
// lib/query-keys.js
export const keys = {
  sessions: ["chat-sessions"],
  session: (id) => ["chat-sessions", id],
  sessionAnalytics: (id) => ["chat-sessions", id, "analytics"],
  sessionStats: ["chat-sessions", "stats"],
  chatHistory: (id) => ["chat-history", id],
  documents: ["documents"],
  document: (id) => ["documents", id],
  documentStatus: (id) => ["documents", id, "status"],
  preferences: ["preferences"],
  sessionConfig: ["preferences", "session-config"],
  usageStats: (days) => ["token-usage", "stats", days],
  dailyUsage: (date) => ["token-usage", "daily", date],
  checkLimits: ["token-usage", "limits"],
  modelBreakdown: (days) => ["token-usage", "breakdown", days],
  apiKeys: ["api-keys"],
  apiKeyProviders: ["api-keys", "providers"],
  tools: ["tools"],
  toolRegistry: ["tools", "registry"],
  enabledTools: ["tools", "enabled"],
  userStats: ["admin", "users", "stats"],
  feedbackStats: ["admin", "feedback", "stats"],
  systemPrompts: ["admin", "system-prompts"],
};
```

---

## 4. Component Architecture

### 4.1 Layout (`app/(app)/layout.jsx`)

Server component that:
1. Validates session via `getValidAccessToken` + Django `/users/me/`
2. Fetches user preferences (for theme + defaults)
3. Renders `<Sidebar>`, `<Header>`, and `{children}`

### 4.2 Chat page (`app/(app)/chat/[sessionId]/page.jsx`)

```
┌─────────────┬──────────────────────────────────┐
│  Sidebar    │  Header (session title, actions)  │
│             ├──────────────────────────────────┤
│  Sessions   │  Message list (scrollable)        │
│  - Search   │  ├─ Human message                 │
│  - Pinned   │  ├─ AI message (markdown render)  │
│  - Active   │  ├─ AI message (streaming...)     │
│  - Archived │  │                                │
│             │  Chat input (textarea + send btn) │
│  + New chat │  Token counter · model selector   │
└─────────────┴──────────────────────────────────┘
```

### 4.3 Key component responsibilities

| Component | Type | Responsibility |
|-----------|------|----------------|
| `ChatSidebar` | Client | Session list with search, pin, archive, new chat button. Uses `useSessions`. |
| `ChatMessage` | Client | Renders a single message. Human = plain text, AI = markdown + mermaid. |
| `ChatInput` | Client | Textarea with auto-resize, Enter to send, Shift+Enter for newline. |
| `ChatStream` | Client | Displays streaming chunks from WebSocket until `type: "done"`. |
| `MarkdownRenderer` | Client | Renders AI markdown with syntax highlighting + mermaid diagrams. |
| `DocumentUpload` | Client | Drag-and-drop file upload with progress. Uses `useUploadDocument`. |
| `DocumentStatus` | Client | Polls `useDocumentStatus` every 2s while `processing_status !== "completed"`. |
| `TokenUsageChart` | Client | Bar/line chart of daily usage. Uses `useDailyUsage` + `useModelBreakdown`. |
| `Sidebar` | Client | Navigation: Chat, Documents, Settings, Admin (if admin role). |
| `Header` | Client | User avatar dropdown (profile, settings, logout), theme toggle. |

---

## 5. WebSocket Integration

```js
// lib/ws.js (client)
export async function openChatSocket(sessionId, { onChunk, onMessage, onError, onClose }) {
  const res = await fetch("/api/auth/ws-token");
  if (!res.ok) throw new Error("Not authenticated");
  const { token } = await res.json();

  const host = process.env.NEXT_PUBLIC_WS_HOST;
  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${scheme}://${host}/ws/chat/${sessionId}/?token=${token}`);

  ws.addEventListener("message", (e) => {
    const data = JSON.parse(e.data);
    if (data.type === "token") onChunk?.(data.content);      // streaming chunk
    else if (data.type === "message") onMessage?.(data.content); // final message
    else if (data.type === "done") onClose?.();               // stream complete
    else if (data.type === "error") onError?.(data.content);
  });
  ws.addEventListener("error", () => onError?.("Connection error"));
  return ws;
}
```

**Message protocol (backend → frontend):**
- `{ "type": "token", "content": "..." }` — streaming chunk (append to current AI message)
- `{ "type": "message", "content": "..." }` — final complete message
- `{ "type": "error", "content": "..." }` — error message
- `{ "type": "done" }` — stream finished

**Message protocol (frontend → backend):**
- `{ "message": "user text" }` — send a chat message

---

## 6. Build Phases

### Phase 1 — Chat MVP (core value)
- `app/(app)/layout.jsx` — session validation + sidebar shell
- `app/(app)/chat/page.jsx` — session list sidebar
- `app/(app)/chat/[sessionId]/page.jsx` — active chat
- `lib/hooks/chat-sessions.js` + `lib/hooks/chat-agent.js`
- `lib/ws.js` — WebSocket streaming
- `lib/query-keys.js`
- Components: `ChatSidebar`, `ChatMessage`, `ChatInput`, `ChatStream`, `MarkdownRenderer`
- Tests: session hooks, WebSocket mock

### Phase 2 — Documents
- `app/(app)/documents/page.jsx` + `app/(app)/documents/[id]/page.jsx`
- `lib/hooks/documents.js`
- Components: `DocumentList`, `DocumentUpload`, `DocumentStatus`
- Tests: document hooks, upload mutation

### Phase 3 — Settings
- `app/(app)/settings/` (profile, preferences, api-keys, tools, usage)
- `lib/hooks/preferences.js`, `lib/hooks/api-keys.js`, `lib/hooks/tools.js`, `lib/hooks/token-usage.js`
- Components: `TokenUsageChart`, preference forms, API key manager
- Tests: settings hooks

### Phase 4 — Admin
- `app/(app)/admin/` (dashboard, users, prompts, feedback)
- `lib/hooks/admin.js`
- Components: admin tables, prompt editor, feedback review queue
- Tests: admin hooks

---

## 7. File Creation Checklist

### Lib (data layer)
- [ ] `lib/query-keys.js`
- [ ] `lib/ws.js`
- [ ] `lib/hooks/chat-sessions.js`
- [ ] `lib/hooks/chat-agent.js`
- [ ] `lib/hooks/documents.js`
- [ ] `lib/hooks/preferences.js`
- [ ] `lib/hooks/token-usage.js`
- [ ] `lib/hooks/api-keys.js`
- [ ] `lib/hooks/tools.js`
- [ ] `lib/hooks/admin.js`

### App routes
- [ ] `app/(app)/layout.jsx`
- [ ] `app/(app)/chat/page.jsx`
- [ ] `app/(app)/chat/[sessionId]/page.jsx`
- [ ] `app/(app)/chat/components/ChatSidebar.jsx`
- [ ] `app/(app)/chat/components/ChatMessage.jsx`
- [ ] `app/(app)/chat/components/ChatInput.jsx`
- [ ] `app/(app)/chat/components/ChatStream.jsx`
- [ ] `app/(app)/documents/page.jsx`
- [ ] `app/(app)/documents/[id]/page.jsx`
- [ ] `app/(app)/settings/page.jsx`
- [ ] `app/(app)/settings/profile/page.jsx`
- [ ] `app/(app)/settings/preferences/page.jsx`
- [ ] `app/(app)/settings/api-keys/page.jsx`
- [ ] `app/(app)/settings/tools/page.jsx`
- [ ] `app/(app)/settings/usage/page.jsx`
- [ ] `app/(app)/admin/page.jsx`
- [ ] `app/(app)/admin/users/page.jsx`
- [ ] `app/(app)/admin/prompts/page.jsx`
- [ ] `app/(app)/admin/feedback/page.jsx`

### Shared components
- [ ] `app/components/layout/Sidebar.jsx`
- [ ] `app/components/layout/Header.jsx`
- [ ] `app/components/chat/MarkdownRenderer.jsx`
- [ ] `app/components/chat/TokenCounter.jsx`

### Tests
- [ ] `tests/chat-sessions.test.jsx`
- [ ] `tests/chat-agent.test.jsx`
- [ ] `tests/documents.test.jsx`
- [ ] `tests/preferences.test.jsx`
- [ ] `tests/ws.test.js`

---

## 8. Conventions

1. **All data hooks go through the BFF proxy** — `fetch("/api/proxy/chatbot/...")`. Never call Django directly from client components.
2. **Server Components use `lib/api.js`** (`apiFetch`) — calls Django directly with the access token.
3. **Query keys are centralized** in `lib/query-keys.js` — mutations invalidate via `queryClient.invalidateQueries({ queryKey: keys.sessions })`.
4. **File uploads use `FormData`** — the proxy passes the raw body through; set `Content-Type: multipart/form-data` and don't override it.
5. **Polling**: `useDocumentStatus` polls every 2s with `refetchInterval` until status is `completed` or `failed`.
6. **Optimistic updates**: pin/archive/delete sessions use `onMutate` to update the cache before the server responds.
7. **Error handling**: all hooks throw errors with `.status` and `.data` — components render error states via `isError`.
8. **Admin routes**: guarded by `role === "admin"` check in the `(app)/admin/` layout (server-side, reads user from `/api/auth/me`).