// tests/chat-sessions.test.jsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import {
  useSessions,
  useSession,
  useCreateSession,
  useUpdateSession,
  useDeleteSession,
  useArchiveSession,
  usePinSession,
  useSessionStats,
} from "@/lib/hooks/chat-sessions";

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }) {
    return (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    );
  };
}

beforeEach(() => vi.restoreAllMocks());
afterEach(() => vi.unstubAllGlobals());

describe("useSessions", () => {
  it("fetches sessions from the proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify([
            { id: "s1", title: "Chat 1", is_active: true },
            { id: "s2", title: "Chat 2", is_active: true },
          ]),
          { status: 200 },
        ),
      ),
    );

    const { result } = renderHook(() => useSessions(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(2);
    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/chat-sessions/",
      expect.objectContaining({ headers: {} }),
    );
  });

  it("passes query params through", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify([]), { status: 200 }),
      ),
    );

    const { result } = renderHook(() => useSessions("?is_active=true"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/chat-sessions/?is_active=true",
      expect.any(Object),
    );
  });

  it("returns error state on 500", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "Server error" }), {
          status: 500,
        }),
      ),
    );

    const { result } = renderHook(() => useSessions(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});

describe("useSession", () => {
  it("fetches a single session by id", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ id: "s1", title: "My Chat", model_name: "gpt-4" }),
          { status: 200 },
        ),
      ),
    );

    const { result } = renderHook(() => useSession("s1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data.title).toBe("My Chat");
  });

  it("does not fetch when id is falsy", async () => {
    vi.stubGlobal("fetch", vi.fn());

    const { result } = renderHook(() => useSession(null), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(fetch).not.toHaveBeenCalled();
  });
});

describe("useCreateSession", () => {
  it("POSTs to chat-sessions/ and invalidates the list", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ id: "new-1", title: "New Chat" }),
          { status: 201 },
        ),
      ),
    );

    const { result } = renderHook(() => useCreateSession(), {
      wrapper: createWrapper(),
    });

    await result.current.mutateAsync({ title: "New Chat" });

    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/chat-sessions/",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ title: "New Chat" }),
      }),
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });

  it("exposes error on 500", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ detail: "User has no ai_preferences" }),
          { status: 500 },
        ),
      ),
    );

    const { result } = renderHook(() => useCreateSession(), {
      wrapper: createWrapper(),
    });

    try {
      await result.current.mutateAsync({ title: "test" });
    } catch {
      // expected
    }

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error.status).toBe(500);
  });
});

describe("useUpdateSession", () => {
  it("PATCHes a session", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ id: "s1", title: "Updated" }),
          { status: 200 },
        ),
      ),
    );

    const { result } = renderHook(() => useUpdateSession(), {
      wrapper: createWrapper(),
    });

    await result.current.mutateAsync({ id: "s1", title: "Updated" });

    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/chat-sessions/s1/",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ title: "Updated" }),
      }),
    );
  });
});

describe("useDeleteSession", () => {
  it("DELETEs a session", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(null, { status: 204 })),
    );

    const { result } = renderHook(() => useDeleteSession(), {
      wrapper: createWrapper(),
    });

    await result.current.mutateAsync("s1");

    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/chat-sessions/s1/",
      expect.objectContaining({ method: "DELETE" }),
    );
  });
});

describe("useArchiveSession", () => {
  it("POSTs to archive endpoint", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ id: "s1", is_archived: true }),
          { status: 200 },
        ),
      ),
    );

    const { result } = renderHook(() => useArchiveSession(), {
      wrapper: createWrapper(),
    });

    await result.current.mutateAsync("s1");

    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/chat-sessions/s1/archive/",
      expect.objectContaining({ method: "POST" }),
    );
  });
});

describe("usePinSession", () => {
  it("POSTs to pin endpoint", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ id: "s1", is_pinned: true }),
          { status: 200 },
        ),
      ),
    );

    const { result } = renderHook(() => usePinSession(), {
      wrapper: createWrapper(),
    });

    await result.current.mutateAsync("s1");

    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/chat-sessions/s1/pin/",
      expect.objectContaining({ method: "POST" }),
    );
  });
});

describe("useSessionStats", () => {
  it("fetches stats from the proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            total_sessions: 10,
            active_sessions: 5,
            archived_sessions: 3,
            total_messages: 42,
            total_tokens: 85000,
            avg_tokens_per_session: 8500,
          }),
          { status: 200 },
        ),
      ),
    );

    const { result } = renderHook(() => useSessionStats(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data.total_sessions).toBe(10);
    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/chat-sessions/stats/",
      expect.any(Object),
    );
  });
});