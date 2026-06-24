// tests/token-usage.test.jsx
//
// Test suite for the Phase 3 token-usage data hooks.
//
// These tests verify the contracts that the token-usage hooks guarantee to
// the rest of the frontend:
//   1. Every hook calls the BFF proxy at the correct path with the correct
//      query parameters — never Django directly.
//   2. `useUsageStats(days)` fetches aggregate stats for the lookback window.
//   3. `useDailyUsage(date)` fetches per-day breakdown and respects `enabled`.
//   4. `useCheckLimits(additionalTokens)` checks daily message/token limits.
//   5. `useModelBreakdown(days)` fetches per-model usage breakdown.
//   6. Errors are decorated with `status` and `data` for callers.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";

import {
  useUsageStats,
  useDailyUsage,
  useCheckLimits,
  useModelBreakdown,
} from "@/lib/hooks/token-usage";
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

const sampleUsageStats = {
  period_days: 30,
  total_requests: 500,
  total_tokens: 250000,
  total_cost: 12.5,
  avg_tokens_per_request: 500,
  avg_cost_per_request: 0.025,
  daily_average: { requests: 16, tokens: 8333, cost: 0.42 },
};

const sampleDailyUsage = {
  date: "2026-06-24",
  request_count: 20,
  total_tokens: 10000,
  total_cost: 0.5,
  by_model: {
    "gpt-4o": { requests: 15, tokens: 8000, cost: 0.4 },
    "gpt-4o-mini": { requests: 5, tokens: 2000, cost: 0.1 },
  },
};

const sampleCheckLimits = {
  exceeded_message_limit: false,
  exceeded_token_limit: false,
  current_messages_today: 10,
  daily_message_limit: 100,
  messages_remaining: 90,
  current_tokens_today: 5000,
  daily_token_limit: 100000,
  tokens_remaining: 95000,
  would_exceed_with_additional: false,
  can_proceed: true,
};

const sampleModelBreakdown = {
  period_days: 30,
  models: [
    {
      model_name: "gpt-4o",
      request_count: 300,
      total_tokens: 200000,
      total_cost: 10.0,
      percentage: 80.0,
    },
    {
      model_name: "gpt-4o-mini",
      request_count: 200,
      total_tokens: 50000,
      total_cost: 2.5,
      percentage: 20.0,
    },
  ],
};

beforeEach(() => vi.restoreAllMocks());
afterEach(() => vi.unstubAllGlobals());

// ---------------------------------------------------------------------------
// useUsageStats
// ---------------------------------------------------------------------------

describe("useUsageStats", () => {
  it("fetches aggregate usage stats for the given lookback window", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse(sampleUsageStats)),
    );

    const { result } = renderHook(() => useUsageStats(30), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data.total_requests).toBe(500);
    expect(result.current.data.total_tokens).toBe(250000);
    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/token-usage/usage-stats/?days=30",
      expect.objectContaining({ headers: {} }),
    );
  });

  it("defaults to 30 days when no argument is provided", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse(sampleUsageStats)),
    );

    const { result } = renderHook(() => useUsageStats(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/token-usage/usage-stats/?days=30",
      expect.any(Object),
    );
  });

  it("uses a different lookback window when specified", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse({ ...sampleUsageStats, period_days: 7 })),
    );

    const { result } = renderHook(() => useUsageStats(7), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/token-usage/usage-stats/?days=7",
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

    const { result } = renderHook(() => useUsageStats(30), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error.status).toBe(500);
  });
});

// ---------------------------------------------------------------------------
// useDailyUsage
// ---------------------------------------------------------------------------

describe("useDailyUsage", () => {
  it("fetches daily usage for a specific date", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse(sampleDailyUsage)),
    );

    const { result } = renderHook(() => useDailyUsage("2026-06-24"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data.request_count).toBe(20);
    expect(result.current.data.by_model["gpt-4o"].tokens).toBe(8000);
    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/token-usage/daily-usage/?date=2026-06-24",
      expect.any(Object),
    );
  });

  it("does not fetch when date is falsy", async () => {
    vi.stubGlobal("fetch", vi.fn());

    const { result } = renderHook(() => useDailyUsage(null), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(fetch).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// useCheckLimits
// ---------------------------------------------------------------------------

describe("useCheckLimits", () => {
  it("fetches limit status with no additional tokens by default", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse(sampleCheckLimits)),
    );

    const { result } = renderHook(() => useCheckLimits(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data.can_proceed).toBe(true);
    expect(result.current.data.messages_remaining).toBe(90);
    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/token-usage/check-limits/?additional_tokens=0",
      expect.any(Object),
    );
  });

  it("passes additional_tokens query param through", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse({ ...sampleCheckLimits, would_exceed_with_additional: true, can_proceed: false }),
      ),
    );

    const { result } = renderHook(() => useCheckLimits(500), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data.can_proceed).toBe(false);
    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/token-usage/check-limits/?additional_tokens=500",
      expect.any(Object),
    );
  });
});

// ---------------------------------------------------------------------------
// useModelBreakdown
// ---------------------------------------------------------------------------

describe("useModelBreakdown", () => {
  it("fetches per-model usage breakdown for the given lookback window", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse(sampleModelBreakdown)),
    );

    const { result } = renderHook(() => useModelBreakdown(30), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data.models).toHaveLength(2);
    expect(result.current.data.models[0].model_name).toBe("gpt-4o");
    expect(result.current.data.models[0].percentage).toBe(80.0);
    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/token-usage/model-breakdown/?days=30",
      expect.any(Object),
    );
  });

  it("defaults to 30 days when no argument is provided", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse(sampleModelBreakdown)),
    );

    const { result } = renderHook(() => useModelBreakdown(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(fetch).toHaveBeenCalledWith(
      "/api/proxy/chatbot/token-usage/model-breakdown/?days=30",
      expect.any(Object),
    );
  });

  it("surfaces error state on 403", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse({ detail: "Forbidden" }, 403),
      ),
    );

    const { result } = renderHook(() => useModelBreakdown(30), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error.status).toBe(403);
    expect(result.current.error.data.detail).toBe("Forbidden");
  });
});