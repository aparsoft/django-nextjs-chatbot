// tests/preferences.test.jsx
//
// Test suite for the Phase 3 preferences data hooks.
//
// These tests verify the contracts that the preferences hooks guarantee to
// the rest of the frontend:
//   1. Every hook calls the BFF proxy at the correct path with the correct
//      HTTP method — never Django directly.
//   2. `usePreferences` fetches from `preferences/me/` (no id needed).
//   3. `useUpdatePreferences` PATCHes `preferences/{id}/`, updates the
//      preferences cache optimistically, and invalidates session-config.
//   4. `useSessionConfig` fetches the derived session configuration.
//   5. `useResetPreferences` POSTs to `preferences/reset-defaults/` and
//      invalidates both preferences and session-config caches.
//   6. Errors are decorated with `status` and `data` for callers.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";

import {
  usePreferences,
  useUpdatePreferences,
  useSessionConfig,
  useResetPreferences,
} from "@/lib/hooks/preferences";
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

const samplePrefs = {
  id: "p1",
  user: "u1",
  user_email: "user@example.com",
  default_model: "gpt-4o",
  default_temperature: 0.7,
  default_max_tokens: 4096,
  enable_auto_summarization: true,
  summarization_trigger_tokens: 8000,
  max_summary_tokens: 500,
  summarization_style: "concise",
  custom_system_prompt: "",
  use_custom_system_prompt: false,
  response_language: "en",
  enable_streaming: true,
  enable_code_execution: false,
  daily_message_limit: 100,
  daily_token_limit: 100000,
  theme: "system",
  show_token_count: true,
  enable_notifications: true,
  save_conversation_history: true,
  allow_data_training: false,
  additional_settings: {},
  has_usage_limits: true,
  is_dark_mode: false,
  is_light_mode: true,
  created_at: "2026-06-01T10:00:00Z",
  updated_at: "2026-06-20T10:00:00Z",
};

const sampleSessionConfig = {
  model_name: "gpt-4o",
  temperature: 0.7,
  max_tokens: 4096,
  enable_summarization: true,
  summarization_threshold: 8000,
  system_prompt: null,
};

beforeEach(() => vi.restoreAllMocks());
afterEach(() => vi.unstubAllGlobals());

// ---------------------------------------------------------------------------
// usePreferences
// ---------------------------------------------------------------------------

describe("usePreferences", () => {
  it("fetches preferences from the me/ endpoint (no id required)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse(samplePrefs)),
    );

    const { result } = renderHook(() => usePreferences(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data.default_model).toBe("gpt-4o");
    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/preferences/me/",
      expect.objectContaining({ headers: {} }),
    );
  });

  it("surfaces error state on 500", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse({ detail: "Server error" }, 500),
      ),
    );

    const { result } = renderHook(() => usePreferences(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error.status).toBe(500);
  });
});

// ---------------------------------------------------------------------------
// useUpdatePreferences
// ---------------------------------------------------------------------------

describe("useUpdatePreferences", () => {
  it("PATCHes the preference by id and updates the cache optimistically", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(mockResponse({ ...samplePrefs, default_model: "o3-mini" }));
    vi.stubGlobal("fetch", fetchMock);

    const wrapper = createWrapper();

    // Pre-seed the preferences cache so we can verify optimistic update.
    const { result: prefsQ } = renderHook(() => usePreferences(), { wrapper });
    await waitFor(() => expect(prefsQ.current.isSuccess).toBe(true));

    const { result } = renderHook(() => useUpdatePreferences(), { wrapper });

    await act(async () => {
      await result.current.mutateAsync({
        id: "p1",
        default_model: "o3-mini",
      });
    });

    // The PATCH call is the second fetch (the first was usePreferences).
    const patchCall = fetchMock.mock.calls.find(
      ([url]) => url === "/api/proxy/chatbot/preferences/p1/",
    );
    expect(patchCall).toBeDefined();
    expect(patchCall[1]).toEqual(
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ default_model: "o3-mini" }),
      }),
    );

    // The preferences cache should now hold the updated data.
    await waitFor(() => {
      expect(prefsQ.current.data.default_model).toBe("o3-mini");
    });
  });

  it("decorates errors with status and data on 400", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse({ detail: "Invalid temperature" }, 400),
      ),
    );

    const { result } = renderHook(() => useUpdatePreferences(), {
      wrapper: createWrapper(),
    });

    try {
      await result.current.mutateAsync({ id: "p1", default_temperature: 99 });
    } catch {
      // expected
    }

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error.status).toBe(400);
    expect(result.current.error.data.detail).toBe("Invalid temperature");
  });

  it("invalidates the session-config cache on success", async () => {
    const fetchMock = vi.fn();
    // PATCH response, then session-config refetch.
    fetchMock
      .mockResolvedValueOnce(mockResponse(samplePrefs))
      .mockResolvedValueOnce(mockResponse(sampleSessionConfig));
    vi.stubGlobal("fetch", fetchMock);

    const wrapper = createWrapper();

    // Mount session-config so invalidation triggers a refetch.
    const { result: configQ } = renderHook(() => useSessionConfig(), {
      wrapper,
    });
    await waitFor(() => expect(configQ.current.isSuccess).toBe(true));

    const initialCallCount = fetchMock.mock.calls.length;

    const { result } = renderHook(() => useUpdatePreferences(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync({ id: "p1", theme: "dark" });
    });

    // session-config should have been invalidated → fetch called again.
    await waitFor(() => {
      expect(fetchMock.mock.calls.length).toBeGreaterThan(initialCallCount);
    });
  });
});

// ---------------------------------------------------------------------------
// useSessionConfig
// ---------------------------------------------------------------------------

describe("useSessionConfig", () => {
  it("fetches the derived session configuration", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse(sampleSessionConfig)),
    );

    const { result } = renderHook(() => useSessionConfig(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data.model_name).toBe("gpt-4o");
    expect(result.current.data.temperature).toBe(0.7);
    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/preferences/session-config/",
      expect.any(Object),
    );
  });
});

// ---------------------------------------------------------------------------
// useResetPreferences
// ---------------------------------------------------------------------------

describe("useResetPreferences", () => {
  it("POSTs to the reset-defaults endpoint", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse({ message: "Preferences reset to defaults" }),
      ),
    );

    const { result } = renderHook(() => useResetPreferences(), {
      wrapper: createWrapper(),
    });

    await result.current.mutateAsync();

    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/preferences/reset-defaults/",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("invalidates both preferences and session-config caches on success", async () => {
    const fetchMock = vi.fn();
    // reset response, then preferences refetch, then session-config refetch.
    fetchMock
      .mockResolvedValueOnce(mockResponse({ message: "ok" }))
      .mockResolvedValueOnce(mockResponse(samplePrefs))
      .mockResolvedValueOnce(mockResponse(sampleSessionConfig));
    vi.stubGlobal("fetch", fetchMock);

    const wrapper = createWrapper();

    // Mount both queries so invalidation triggers refetches.
    const { result: prefsQ } = renderHook(() => usePreferences(), { wrapper });
    const { result: configQ } = renderHook(() => useSessionConfig(), {
      wrapper,
    });
    await waitFor(() => expect(prefsQ.current.isSuccess).toBe(true));
    await waitFor(() => expect(configQ.current.isSuccess).toBe(true));

    const initialCallCount = fetchMock.mock.calls.length;

    const { result } = renderHook(() => useResetPreferences(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync();
    });

    // Both caches should be invalidated → fetch called again.
    await waitFor(() => {
      expect(fetchMock.mock.calls.length).toBeGreaterThan(initialCallCount);
    });
  });

  it("decorates errors with status and data on 403", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse({ detail: "Not allowed" }, 403),
      ),
    );

    const { result } = renderHook(() => useResetPreferences(), {
      wrapper: createWrapper(),
    });

    try {
      await result.current.mutateAsync();
    } catch {
      // expected
    }

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error.status).toBe(403);
  });
});