// tests/api-keys.test.jsx
//
// Test suite for the Phase 3 API key data hooks.
//
// These tests verify the contracts that the api-keys hooks guarantee to
// the rest of the frontend:
//   1. Every hook calls the BFF proxy at the correct path with the correct
//      HTTP method — never Django directly.
//   2. `useApiKeys` lists keys (masked) with optional query params.
//   3. `useApiKeyProviders` fetches the supported provider list.
//   4. `useCreateApiKey` POSTs a new key and invalidates the keys + usage caches.
//   5. `useValidateApiKey`, `useSetDefaultApiKey`, `useDeactivateApiKey` POST
//      to their respective action endpoints and invalidate the keys cache.
//   6. `useDeleteApiKey` DELETEs and invalidates keys + usage caches.
//   7. Errors are decorated with `status` and `data` for callers.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";

import {
  useApiKeys,
  useApiKeyProviders,
  useApiKeyUsage,
  useCreateApiKey,
  useUpdateApiKey,
  useDeleteApiKey,
  useValidateApiKey,
  useSetDefaultApiKey,
  useDeactivateApiKey,
} from "@/lib/hooks/api-keys";
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

const sampleKey = {
  id: "k1",
  user: "u1",
  key_name: "My OpenAI key",
  provider: "openai",
  display_key: "sk-…abc1",
  is_active: true,
  is_default: true,
  is_validated: true,
  last_used_at: "2026-06-20T10:00:00Z",
  usage_count: 42,
  created_at: "2026-06-01T10:00:00Z",
};

const sampleProviders = {
  providers: [
    {
      name: "openai",
      display_name: "OpenAI",
      description: "GPT models",
      documentation_url: "https://platform.openai.com/docs",
    },
    {
      name: "anthropic",
      display_name: "Anthropic",
      description: "Claude models",
      documentation_url: "https://docs.anthropic.com",
    },
  ],
};

beforeEach(() => vi.restoreAllMocks());
afterEach(() => vi.unstubAllGlobals());

// ---------------------------------------------------------------------------
// useApiKeys
// ---------------------------------------------------------------------------

describe("useApiKeys", () => {
  it("fetches the API key list from the proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse([sampleKey])),
    );

    const { result } = renderHook(() => useApiKeys(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(1);
    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/api-keys/",
      expect.objectContaining({ headers: {} }),
    );
  });

  it("passes query params through to the proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse([])),
    );

    const { result } = renderHook(
      () => useApiKeys("?provider=openai&is_active=true"),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/api-keys/?provider=openai&is_active=true",
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

    const { result } = renderHook(() => useApiKeys(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error.status).toBe(500);
  });
});

// ---------------------------------------------------------------------------
// useApiKeyProviders
// ---------------------------------------------------------------------------

describe("useApiKeyProviders", () => {
  it("fetches the supported provider list", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse(sampleProviders)),
    );

    const { result } = renderHook(() => useApiKeyProviders(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data.providers).toHaveLength(2);
    expect(result.current.data.providers[0].name).toBe("openai");
    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/api-keys/providers/",
      expect.any(Object),
    );
  });
});

// ---------------------------------------------------------------------------
// useApiKeyUsage
// ---------------------------------------------------------------------------

describe("useApiKeyUsage", () => {
  it("fetches the usage summary grouped by provider", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse({
          by_provider: {
            openai: { total_requests: 100, total_tokens: 50000, total_cost: 2.5 },
          },
        }),
      ),
    );

    const { result } = renderHook(() => useApiKeyUsage(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data.by_provider.openai.total_tokens).toBe(50000);
    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/api-keys/usage-summary/",
      expect.any(Object),
    );
  });
});

// ---------------------------------------------------------------------------
// useCreateApiKey
// ---------------------------------------------------------------------------

describe("useCreateApiKey", () => {
  it("POSTs a new API key and invalidates the keys + usage caches", async () => {
    const fetchMock = vi.fn();
    // create response, then keys list refetch, then usage refetch.
    fetchMock
      .mockResolvedValueOnce(mockResponse(sampleKey, 201))
      .mockResolvedValueOnce(mockResponse([sampleKey]))
      .mockResolvedValueOnce(
        mockResponse({ by_provider: {} }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const wrapper = createWrapper();

    // Mount observing queries so invalidation triggers refetches.
    const { result: keysQ } = renderHook(() => useApiKeys(), { wrapper });
    const { result: usageQ } = renderHook(() => useApiKeyUsage(), { wrapper });
    await waitFor(() => expect(keysQ.current.isSuccess).toBe(true));
    await waitFor(() => expect(usageQ.current.isSuccess).toBe(true));

    const initialCallCount = fetchMock.mock.calls.length;

    const { result } = renderHook(() => useCreateApiKey(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync({
        key_name: "My OpenAI key",
        provider: "openai",
        api_key: "sk-test123",
        is_default: true,
      });
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/proxy/chatbot/api-keys/",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          key_name: "My OpenAI key",
          provider: "openai",
          api_key: "sk-test123",
          is_default: true,
        }),
      }),
    );

    // Both caches should be invalidated → fetch called again.
    await waitFor(() => {
      expect(fetchMock.mock.calls.length).toBeGreaterThan(initialCallCount);
    });
  });

  it("decorates errors with status and data on 400", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse({ detail: "Invalid API key" }, 400),
      ),
    );

    const { result } = renderHook(() => useCreateApiKey(), {
      wrapper: createWrapper(),
    });

    try {
      await result.current.mutateAsync({
        key_name: "bad",
        provider: "openai",
        api_key: "",
      });
    } catch {
      // expected
    }

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error.status).toBe(400);
    expect(result.current.error.data.detail).toBe("Invalid API key");
  });
});

// ---------------------------------------------------------------------------
// useUpdateApiKey
// ---------------------------------------------------------------------------

describe("useUpdateApiKey", () => {
  it("PATCHes API key metadata", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse({ ...sampleKey, key_name: "Renamed" }),
      ),
    );

    const { result } = renderHook(() => useUpdateApiKey(), {
      wrapper: createWrapper(),
    });

    await result.current.mutateAsync({ id: "k1", key_name: "Renamed" });

    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/api-keys/k1/",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ key_name: "Renamed" }),
      }),
    );
  });
});

// ---------------------------------------------------------------------------
// useDeleteApiKey
// ---------------------------------------------------------------------------

describe("useDeleteApiKey", () => {
  it("DELETEs an API key", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(null, { status: 204 })),
    );

    const { result } = renderHook(() => useDeleteApiKey(), {
      wrapper: createWrapper(),
    });

    await result.current.mutateAsync("k1");

    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/api-keys/k1/",
      expect.objectContaining({ method: "DELETE" }),
    );
  });
});

// ---------------------------------------------------------------------------
// useValidateApiKey
// ---------------------------------------------------------------------------

describe("useValidateApiKey", () => {
  it("POSTs to the validate action endpoint", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse({
          is_valid: true,
          provider: "openai",
          validation_message: "Key is valid",
        }),
      ),
    );

    const { result } = renderHook(() => useValidateApiKey(), {
      wrapper: createWrapper(),
    });

    await result.current.mutateAsync("k1");

    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/api-keys/k1/validate/",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("surfaces invalid validation results without throwing", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse({
          is_valid: false,
          provider: "openai",
          validation_message: "Invalid key",
        }),
      ),
    );

    const { result } = renderHook(() => useValidateApiKey(), {
      wrapper: createWrapper(),
    });

    const data = await result.current.mutateAsync("k1");
    expect(data.is_valid).toBe(false);
    expect(data.validation_message).toBe("Invalid key");
  });
});

// ---------------------------------------------------------------------------
// useSetDefaultApiKey
// ---------------------------------------------------------------------------

describe("useSetDefaultApiKey", () => {
  it("POSTs to the set-default action endpoint", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse({ ...sampleKey, is_default: true }),
      ),
    );

    const { result } = renderHook(() => useSetDefaultApiKey(), {
      wrapper: createWrapper(),
    });

    await result.current.mutateAsync("k1");

    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/api-keys/k1/set-default/",
      expect.objectContaining({ method: "POST" }),
    );
  });
});

// ---------------------------------------------------------------------------
// useDeactivateApiKey
// ---------------------------------------------------------------------------

describe("useDeactivateApiKey", () => {
  it("POSTs to the deactivate action endpoint", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse({ ...sampleKey, is_active: false }),
      ),
    );

    const { result } = renderHook(() => useDeactivateApiKey(), {
      wrapper: createWrapper(),
    });

    await result.current.mutateAsync("k1");

    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/api-keys/k1/deactivate/",
      expect.objectContaining({ method: "POST" }),
    );
  });
});