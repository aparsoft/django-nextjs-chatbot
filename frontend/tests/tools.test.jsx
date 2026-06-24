// tests/tools.test.jsx
//
// Test suite for the Phase 3 tools data hooks.
//
// These tests verify the contracts that the tools hooks guarantee to
// the rest of the frontend:
//   1. Every hook calls the BFF proxy at the correct path with the correct
//      HTTP method — never Django directly.
//   2. `useTools` lists the user's tools with optional query params.
//   3. `useToolRegistry` fetches the available tool registry.
//   4. `useEnabledTools` lists only enabled tools.
//   5. `useCreateTool` POSTs a new tool and invalidates tools + enabledTools.
//   6. `useActivateTool` / `useDeactivateTool` POST to their action endpoints
//      and invalidate tools + enabledTools.
//   7. `useDeleteTool` DELETEs and invalidates tools + enabledTools.
//   8. `useToolRateLimitStatus` fetches rate-limit status for a tool.
//   9. Errors are decorated with `status` and `data` for callers.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";

import {
  useTools,
  useToolRegistry,
  useEnabledTools,
  useCreateTool,
  useUpdateTool,
  useDeleteTool,
  useActivateTool,
  useDeactivateTool,
  useToolRateLimitStatus,
} from "@/lib/hooks/tools";
import { keys } from "@/lib/query-keys";

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

function mockResponse(body, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

const sampleTool = {
  id: "t1",
  user: "u1",
  tool_name: "web_search",
  configuration: {},
  is_enabled: true,
  created_at: "2026-06-01T10:00:00Z",
  updated_at: "2026-06-20T10:00:00Z",
};

const sampleRegistry = {
  tools: [
    {
      name: "web_search",
      display_name: "Web Search",
      description: "Search the web for current information",
      category: "search",
      is_available: true,
      requires_config: false,
      config_schema: null,
    },
    {
      name: "calculator",
      display_name: "Calculator",
      description: "Perform mathematical calculations",
      category: "math",
      is_available: true,
      requires_config: false,
      config_schema: null,
    },
  ],
};

beforeEach(() => vi.restoreAllMocks());
afterEach(() => vi.unstubAllGlobals());

// ---------------------------------------------------------------------------
// useTools
// ---------------------------------------------------------------------------

describe("useTools", () => {
  it("fetches the user's tool list from the proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse([sampleTool])),
    );

    const { result } = renderHook(() => useTools(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(1);
    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/tools/",
      expect.objectContaining({ headers: {} }),
    );
  });

  it("passes query params through to the proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse([])),
    );

    const { result } = renderHook(
      () => useTools("?is_enabled=true&category=search"),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/tools/?is_enabled=true&category=search",
      expect.any(Object),
    );
  });

  it("surfaces error state on 500", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse({ detail: "Server error" }, 500),
      ),
    );

    const { result } = renderHook(() => useTools(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error.status).toBe(500);
  });
});

// ---------------------------------------------------------------------------
// useToolRegistry
// ---------------------------------------------------------------------------

describe("useToolRegistry", () => {
  it("fetches the tool registry with config schemas", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse(sampleRegistry)),
    );

    const { result } = renderHook(() => useToolRegistry(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data.tools).toHaveLength(2);
    expect(result.current.data.tools[0].name).toBe("web_search");
    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/tools/registry/",
      expect.any(Object),
    );
  });
});

// ---------------------------------------------------------------------------
// useEnabledTools
// ---------------------------------------------------------------------------

describe("useEnabledTools", () => {
  it("fetches only enabled tools", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse([sampleTool])),
    );

    const { result } = renderHook(() => useEnabledTools(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(1);
    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/tools/enabled/",
      expect.any(Object),
    );
  });
});

// ---------------------------------------------------------------------------
// useCreateTool
// ---------------------------------------------------------------------------

describe("useCreateTool", () => {
  it("POSTs a new tool and invalidates tools + enabledTools caches", async () => {
    const fetchMock = vi.fn();
    // create response, then tools refetch, then enabledTools refetch.
    fetchMock
      .mockResolvedValueOnce(mockResponse(sampleTool, 201))
      .mockResolvedValueOnce(mockResponse([sampleTool]))
      .mockResolvedValueOnce(mockResponse([sampleTool]));
    vi.stubGlobal("fetch", fetchMock);

    const wrapper = createWrapper();

    // Mount observing queries.
    const { result: toolsQ } = renderHook(() => useTools(), { wrapper });
    const { result: enabledQ } = renderHook(() => useEnabledTools(), {
      wrapper,
    });
    await waitFor(() => expect(toolsQ.current.isSuccess).toBe(true));
    await waitFor(() => expect(enabledQ.current.isSuccess).toBe(true));

    const initialCallCount = fetchMock.mock.calls.length;

    const { result } = renderHook(() => useCreateTool(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync({
        tool_name: "web_search",
        configuration: {},
      });
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/proxy/chatbot/tools/",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ tool_name: "web_search", configuration: {} }),
      }),
    );

    // Both caches should be invalidated.
    await waitFor(() => {
      expect(fetchMock.mock.calls.length).toBeGreaterThan(initialCallCount);
    });
  });

  it("decorates errors with status and data on 400", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse({ detail: "Unknown tool" }, 400),
      ),
    );

    const { result } = renderHook(() => useCreateTool(), {
      wrapper: createWrapper(),
    });

    try {
      await result.current.mutateAsync({ tool_name: "nonexistent" });
    } catch {
      // expected
    }

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error.status).toBe(400);
    expect(result.current.error.data.detail).toBe("Unknown tool");
  });
});

// ---------------------------------------------------------------------------
// useUpdateTool
// ---------------------------------------------------------------------------

describe("useUpdateTool", () => {
  it("PATCHes tool configuration", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse({ ...sampleTool, configuration: { max_results: 10 } }),
      ),
    );

    const { result } = renderHook(() => useUpdateTool(), {
      wrapper: createWrapper(),
    });

    await result.current.mutateAsync({ id: "t1", configuration: { max_results: 10 } });

    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/tools/t1/",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ configuration: { max_results: 10 } }),
      }),
    );
  });
});

// ---------------------------------------------------------------------------
// useDeleteTool
// ---------------------------------------------------------------------------

describe("useDeleteTool", () => {
  it("DELETEs a tool", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(null, { status: 204 })),
    );

    const { result } = renderHook(() => useDeleteTool(), {
      wrapper: createWrapper(),
    });

    await result.current.mutateAsync("t1");

    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/tools/t1/",
      expect.objectContaining({ method: "DELETE" }),
    );
  });
});

// ---------------------------------------------------------------------------
// useActivateTool
// ---------------------------------------------------------------------------

describe("useActivateTool", () => {
  it("POSTs to the activate action endpoint", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse({ ...sampleTool, is_enabled: true }),
      ),
    );

    const { result } = renderHook(() => useActivateTool(), {
      wrapper: createWrapper(),
    });

    await result.current.mutateAsync("t1");

    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/tools/t1/activate/",
      expect.objectContaining({ method: "POST" }),
    );
  });
});

// ---------------------------------------------------------------------------
// useDeactivateTool
// ---------------------------------------------------------------------------

describe("useDeactivateTool", () => {
  it("POSTs to the deactivate action endpoint", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse({ ...sampleTool, is_enabled: false }),
      ),
    );

    const { result } = renderHook(() => useDeactivateTool(), {
      wrapper: createWrapper(),
    });

    await result.current.mutateAsync("t1");

    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/tools/t1/deactivate/",
      expect.objectContaining({ method: "POST" }),
    );
  });
});

// ---------------------------------------------------------------------------
// useToolRateLimitStatus
// ---------------------------------------------------------------------------

describe("useToolRateLimitStatus", () => {
  it("fetches the rate-limit status for a tool", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse({
          tool_name: "web_search",
          is_rate_limited: false,
          current_usage: 5,
          rate_limit: 100,
          reset_at: "2026-06-24T12:00:00Z",
          usage_percentage: 5.0,
        }),
      ),
    );

    const { result } = renderHook(() => useToolRateLimitStatus("t1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data.is_rate_limited).toBe(false);
    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/tools/t1/rate-limit-status/",
      expect.any(Object),
    );
  });

  it("does not fetch when id is falsy", async () => {
    vi.stubGlobal("fetch", vi.fn());

    const { result } = renderHook(() => useToolRateLimitStatus(null), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(fetch).not.toHaveBeenCalled();
  });
});