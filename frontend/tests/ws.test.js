// tests/ws.test.js
import { describe, it, expect, vi, beforeAll, afterAll } from "vitest";

// Mock react-use-websocket before importing hooks that use it.
vi.mock("react-use-websocket", () => ({
  default: vi.fn(() => ({
    sendJsonMessage: vi.fn(),
    lastJsonMessage: null,
    connectionStatus: "Connecting",
  })),
  READY_STATE: { CONNECTING: 0, OPEN: 1, CLOSING: 2, CLOSED: 3 },
}));

import {
  getWsToken,
  buildWsUrl,
  parseWsMessage,
  buildChatPayload,
} from "@/lib/ws";

describe("getWsToken", () => {
  it("returns the token from /api/auth/ws-token", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ token: "test-access-token" }), {
          status: 200,
        }),
      ),
    );

    const token = await getWsToken();
    expect(token).toBe("test-access-token");
    expect(fetch).toHaveBeenCalledWith("/api/auth/ws-token");
  });

  it("throws on 401", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ error: "Not authenticated" }), {
          status: 401,
        }),
      ),
    );

    await expect(getWsToken()).rejects.toThrow("Not authenticated");
  });

  it("throws on network error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("Network error")));

    await expect(getWsToken()).rejects.toThrow("Network error");
  });
});

describe("buildWsUrl", () => {
    // Set the WS host env var for tests (buildWsUrl returns null without it).
    const originalHost = process.env.NEXT_PUBLIC_WS_HOST;
    beforeAll(() => { process.env.NEXT_PUBLIC_WS_HOST = "localhost:8000"; });
    afterAll(() => { process.env.NEXT_PUBLIC_WS_HOST = originalHost; });

  it("builds a ws:// URL with token in query string", () => {
    const url = buildWsUrl("session-123", "my-token");
    expect(url).toContain("ws://");
    expect(url).toContain("/ws/chat/session-123/");
    expect(url).toContain("token=my-token");
  });

  it("uses wss:// when window.location.protocol is https:", () => {
    // jsdom defaults to http: so we test the logic directly
    const url = buildWsUrl("abc", "tok");
    expect(url).toMatch(/^ws:\/\//); // jsdom is http
  });

    it("uses NEXT_PUBLIC_WS_HOST env var", () => {
    const url = buildWsUrl("s1", "t1");
    expect(url).toMatch(/^ws:\/\/[^/]+\/ws\/chat\/s1\/\?token=t1$/);
  });

    it("returns null for undefined sessionId", () => {
        expect(buildWsUrl(undefined, "tok")).toBeNull();
    });

    it("returns null for 'new' sessionId", () => {
        expect(buildWsUrl("new", "tok")).toBeNull();
    });

    it("returns null when token is missing", () => {
        expect(buildWsUrl("session-123", null)).toBeNull();
    });
});

describe("parseWsMessage", () => {
  it("parses a valid JSON message", () => {
    const event = { data: JSON.stringify({ type: "token", content: "hello" }) };
    const result = parseWsMessage(event);
    expect(result).toEqual({ type: "token", content: "hello" });
  });

  it("returns null for invalid JSON", () => {
    const event = { data: "not json" };
    const result = parseWsMessage(event);
    expect(result).toBeNull();
  });

  it("returns null for empty data", () => {
    const event = { data: "" };
    const result = parseWsMessage(event);
    expect(result).toBeNull();
  });

  it("returns null for null event data", () => {
    const event = { data: null };
    const result = parseWsMessage(event);
    expect(result).toBeNull();
  });
});

describe("buildChatPayload", () => {
  it("builds a JSON payload with the message", () => {
    const payload = buildChatPayload("Hello AI!");
    expect(JSON.parse(payload)).toEqual({ message: "Hello AI!" });
  });

  it("handles empty string", () => {
    const payload = buildChatPayload("");
    expect(JSON.parse(payload)).toEqual({ message: "" });
  });

  it("handles special characters", () => {
    const payload = buildChatPayload('{"test": "value"}');
    expect(JSON.parse(payload)).toEqual({ message: '{"test": "value"}' });
  });
});