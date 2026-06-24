// lib/hooks/chat-sessions.js
// TanStack Query hooks for chat session CRUD + custom actions.
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

/** List chat sessions with optional query filters. */
export function useSessions(params = "") {
  return useQuery({
    queryKey: [...keys.sessions, params],
    queryFn: async () => {
      const data = await proxyFetch(`chat-sessions/${params}`);
      // DRF LimitOffsetPagination returns {count, next, previous, results};
      // non-paginated endpoints return a plain array. Normalize to array.
      return Array.isArray(data) ? data : data?.results ?? [];
    },
    staleTime: 30_000,
  });
}

/** Single session detail. */
export function useSession(id) {
  return useQuery({
    queryKey: keys.session(id),
    queryFn: () => proxyFetch(`chat-sessions/${id}/`),
    enabled: !!id && id !== "new" && id !== "undefined",
  });
}

/** Create a new chat session. */
export function useCreateSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body) =>
      proxyFetch("chat-sessions/", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.sessions }),
  });
}

/** Update a session (title, temperature, etc.). */
export function useUpdateSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }) =>
      proxyFetch(`chat-sessions/${id}/`, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    onSuccess: (data, { id }) => {
      qc.setQueryData(keys.session(id), data);
      qc.invalidateQueries({ queryKey: keys.sessions });
    },
  });
}

/** Delete a session. */
export function useDeleteSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) =>
      proxyFetch(`chat-sessions/${id}/`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.sessions }),
  });
}

/** Archive a session. */
export function useArchiveSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) =>
      proxyFetch(`chat-sessions/${id}/archive/`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.sessions }),
  });
}

/** Pin/unpin a session. */
export function usePinSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) =>
      proxyFetch(`chat-sessions/${id}/pin/`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.sessions }),
  });
}

/** Session stats (dashboard). */
export function useSessionStats() {
  return useQuery({
    queryKey: keys.sessionStats,
    queryFn: () => proxyFetch("chat-sessions/stats/"),
    staleTime: 60_000,
  });
}

/** Per-session analytics. */
export function useSessionAnalytics(id) {
  return useQuery({
    queryKey: keys.sessionAnalytics(id),
    queryFn: () => proxyFetch(`chat-sessions/${id}/analytics/`),
    enabled: !!id,
  });
}