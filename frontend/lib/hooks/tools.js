// lib/hooks/tools.js
// TanStack Query hooks for tool management.
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

/** List the current user's tools. */
export function useTools(params = "") {
  return useQuery({
    queryKey: [...keys.tools, params],
    queryFn: () => proxyFetch(`tools/${params}`),
    staleTime: 30_000,
  });
}

/** Fetch the tool registry (available tools + config schemas). */
export function useToolRegistry() {
  return useQuery({
    queryKey: keys.toolRegistry,
    queryFn: () => proxyFetch("tools/registry/"),
    staleTime: 300_000,
  });
}

/** List only enabled tools. */
export function useEnabledTools() {
  return useQuery({
    queryKey: keys.enabledTools,
    queryFn: () => proxyFetch("tools/enabled/"),
    staleTime: 30_000,
  });
}

/** Create (register) a new tool for the current user. */
export function useCreateTool() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body) =>
      proxyFetch("tools/", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.tools });
      qc.invalidateQueries({ queryKey: keys.enabledTools });
    },
  });
}

/** Update a tool's configuration. */
export function useUpdateTool() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }) =>
      proxyFetch(`tools/${id}/`, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.tools });
      qc.invalidateQueries({ queryKey: keys.enabledTools });
    },
  });
}

/** Delete a tool. */
export function useDeleteTool() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) => proxyFetch(`tools/${id}/`, { method: "DELETE" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.tools });
      qc.invalidateQueries({ queryKey: keys.enabledTools });
    },
  });
}

/** Activate a tool (sets `is_enabled: true`). */
export function useActivateTool() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) =>
      proxyFetch(`tools/${id}/activate/`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.tools });
      qc.invalidateQueries({ queryKey: keys.enabledTools });
    },
  });
}

/** Deactivate a tool (sets `is_enabled: false`). */
export function useDeactivateTool() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) =>
      proxyFetch(`tools/${id}/deactivate/`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.tools });
      qc.invalidateQueries({ queryKey: keys.enabledTools });
    },
  });
}

/** Check the rate-limit status for a specific tool. */
export function useToolRateLimitStatus(id) {
  return useQuery({
    queryKey: [...keys.tools, id, "rate-limit"],
    queryFn: () => proxyFetch(`tools/${id}/rate-limit-status/`),
    enabled: !!id,
    staleTime: 30_000,
  });
}