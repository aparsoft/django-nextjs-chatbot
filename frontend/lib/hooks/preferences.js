// lib/hooks/preferences.js
// TanStack Query hooks for user chat preferences.
// All calls go through the BFF proxy.

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
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
 * Fetch the current user's preferences.
 * Uses the `preferences/me/` convenience endpoint so we don't need
 * to know the preference id ahead of time.
 */
export function usePreferences() {
  return useQuery({
    queryKey: keys.preferences,
    queryFn: () => proxyFetch("preferences/me/"),
    staleTime: 60_000,
  });
}

/**
 * Update the current user's preferences.
 * Accepts the preference `id` plus a partial body. On success the
 * preferences cache is updated optimistically and the session-config
 * cache is invalidated (it derives from preferences).
 */
export function useUpdatePreferences() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }) =>
      proxyFetch(`preferences/${id}/`, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    onSuccess: (data) => {
      qc.setQueryData(keys.preferences, data);
      qc.invalidateQueries({ queryKey: keys.sessionConfig });
    },
  });
}

/**
 * Fetch the session configuration derived from preferences.
 * Returns the model/temperature/max-tokens/summarization config used
 * when starting a new chat session.
 */
export function useSessionConfig() {
  return useQuery({
    queryKey: keys.sessionConfig,
    queryFn: () => proxyFetch("preferences/session-config/"),
    staleTime: 60_000,
  });
}

/**
 * Reset preferences to system defaults.
 * On success, refetch the preferences and session-config caches so
 * the UI reflects the reset values immediately.
 */
export function useResetPreferences() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      proxyFetch("preferences/reset-defaults/", { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.preferences });
      qc.invalidateQueries({ queryKey: keys.sessionConfig });
    },
  });
}