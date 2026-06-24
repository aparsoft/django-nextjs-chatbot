// tests/chat-agent.test.jsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";

// Mock react-use-websocket — we control the returned values.
const mockSendJsonMessage = vi.fn();
let mockLastJsonMessage = null;
let mockConnectionStatus = "Connecting";

vi.mock("react-use-websocket", () => ({
  default: vi.fn(() => ({
    sendJsonMessage: mockSendJsonMessage,
    lastJsonMessage: mockLastJsonMessage,
    connectionStatus: mockConnectionStatus,
  })),
  READY_STATE: { CONNECTING: 0, OPEN: 1, CLOSING: 2, CLOSED: 3 },
}));

import {
  useChatHistory,
  useSendMessage,
  useChatSocket,
} from "@/lib/hooks/chat-agent";

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

beforeEach(() => {
  vi.restoreAllMocks();
  mockSendJsonMessage.mockClear();
  mockLastJsonMessage = null;
  mockConnectionStatus = "Connecting";
});
afterEach(() => vi.unstubAllGlobals());

describe("useChatHistory", () => {
  it("fetches chat history for a session", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify([
            { role: "human", content: "Hello" },
            { role: "ai", content: "Hi there!" },
          ]),
          { status: 200 },
        ),
      ),
    );

    const { result } = renderHook(() => useChatHistory("session-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(2);
    expect(result.current.data[0].role).toBe("human");
    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/chat-agent/history/session-1/",
      expect.any(Object),
    );
  });

  it("does not fetch when sessionId is falsy", async () => {
    vi.stubGlobal("fetch", vi.fn());

    const { result } = renderHook(() => useChatHistory(null), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(fetch).not.toHaveBeenCalled();
  });

  it("returns error on 404", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "Not found" }), { status: 404 }),
      ),
    );

    const { result } = renderHook(() => useChatHistory("bad-id"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});

describe("useSendMessage", () => {
  it("POSTs to chat-agent/send/ and invalidates history", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            response: "AI reply",
            session_id: "s1",
            tokens_used: 42,
            message_count: 3,
          }),
          { status: 200 },
        ),
      ),
    );

    const { result } = renderHook(() => useSendMessage(), {
      wrapper: createWrapper(),
    });

    await result.current.mutateAsync({
      message: "Hello",
      session_id: "s1",
    });

    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/chat-agent/send/",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ message: "Hello", session_id: "s1" }),
      }),
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data.response).toBe("AI reply");
  });
});

describe("useChatSocket", () => {
  it("returns initial state with no streaming", async () => {
    // Mock getWsToken
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ token: "ws-token" }), { status: 200 }),
      ),
    );

    const { result } = renderHook(() => useChatSocket("session-1"), {
      wrapper: createWrapper(),
    });

    // Initial state
    expect(result.current.isStreaming).toBe(false);
    expect(result.current.streamingContent).toBe("");
    expect(result.current.error).toBeNull();
    expect(result.current.connectionStatus).toBe("Connecting");
  });

  it("sendMessage queues message when connection is not open", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ token: "ws-token" }), { status: 200 }),
      ),
    );

    // Connection is "Connecting" — message should be queued, not sent.
    mockConnectionStatus = "Connecting";

    const { result } = renderHook(() => useChatSocket("session-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.connectionStatus).toBeDefined());

    act(() => {
      result.current.sendMessage("Hello AI!");
    });

    // Should set isStreaming but NOT call sendJsonMessage (queued).
    expect(result.current.isStreaming).toBe(true);
    expect(mockSendJsonMessage).not.toHaveBeenCalled();
  });

  it("sendMessage sends immediately when connection is open", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ token: "ws-token" }), { status: 200 }),
      ),
    );

    mockConnectionStatus = "Open";

    const { result } = renderHook(() => useChatSocket("session-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.connectionStatus).toBe("Open"));

    act(() => {
      result.current.sendMessage("Hello!");
    });

    expect(result.current.isStreaming).toBe(true);
    expect(mockSendJsonMessage).toHaveBeenCalledWith({ message: "Hello!" });
  });

  it("sets error when getWsToken fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ error: "Not authenticated" }), {
          status: 401,
        }),
      ),
    );

    const { result } = renderHook(() => useChatSocket("session-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.error).not.toBeNull());
    expect(result.current.error).toBe("Not authenticated");
  });
});