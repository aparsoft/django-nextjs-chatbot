// lib/hooks/token-usage.js
// TanStack Query hooks for token usage stats, daily breakdowns, and limits.
// All calls go through the BFF proxy.

import { useQuery } from "@tanstack/react-query";
import { keys } from "@/lib/query-keys";

async function proxyFetch(path, options = {}) {
  const res = await fetch(`/api/proxy/chatbot/${path.replace(/^\//, "")}`, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const err = new Error(data?.message || data?.detail || `API ${res.status}`);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

/**
 * Aggregate usage stats for the last `days` days.
 * @param {number} days - Lookback window (default 30).
 */
export function useUsageStats(days = 30) {
  return useQuery({
    queryKey: keys.usageStats(days),
    queryFn: () => proxyFetch(`token-usage/usage-stats/?days=${days}`),
    staleTime: 60_000,
  });
}

/**
 * Daily usage breakdown for a specific date.
 * @param {string} date - ISO date string (YYYY-MM-DD). Defaults to today.
 */
export function useDailyUsage(date) {
  return useQuery({
    queryKey: keys.dailyUsage(date),
    queryFn: () => proxyFetch(`token-usage/daily-usage/?date=${date}`),
    enabled: !!date,
    staleTime: 60_000,
  });
}

/**
 * Check whether the user is within their daily message/token limits.
 * Optionally pass `additionalTokens` to check if a pending request
 * would exceed the limit.
 */
export function useCheckLimits(additionalTokens = 0) {
  return useQuery({
    queryKey: [...keys.checkLimits, additionalTokens],
    queryFn: () =>
      proxyFetch(`token-usage/check-limits/?additional_tokens=${additionalTokens}`),
    staleTime: 30_000,
  });
}

/**
 * Per-model usage breakdown for the last `days` days.
 * @param {number} days - Lookback window (default 30).
 */
export function useModelBreakdown(days = 30) {
  return useQuery({
    queryKey: keys.modelBreakdown(days),
    queryFn: () => proxyFetch(`token-usage/model-breakdown/?days=${days}`),
    staleTime: 60_000,
  });
}