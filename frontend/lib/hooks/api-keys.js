// lib/hooks/api-keys.js
// TanStack Query hooks for API key management.
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

/** List the current user's API keys (masked). */
export function useApiKeys(params = "") {
  return useQuery({
    queryKey: [...keys.apiKeys, params],
    queryFn: () => proxyFetch(`api-keys/${params}`),
    staleTime: 30_000,
  });
}

/** List supported API key providers. */
export function useApiKeyProviders() {
  return useQuery({
    queryKey: keys.apiKeyProviders,
    queryFn: () => proxyFetch("api-keys/providers/"),
    staleTime: 300_000,
  });
}

/** Usage summary grouped by provider. */
export function useApiKeyUsage() {
  return useQuery({
    queryKey: keys.apiKeyUsage,
    queryFn: () => proxyFetch("api-keys/usage-summary/"),
    staleTime: 60_000,
  });
}

/**
 * Create a new API key.
 * The raw key is never returned by the backend — only the masked
 * display key and metadata.
 */
export function useCreateApiKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body) =>
      proxyFetch("api-keys/", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.apiKeys });
      qc.invalidateQueries({ queryKey: keys.apiKeyUsage });
    },
  });
}

/** Update an API key's metadata (key_name, metadata). */
export function useUpdateApiKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }) =>
      proxyFetch(`api-keys/${id}/`, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.apiKeys });
    },
  });
}

/** Delete an API key. */
export function useDeleteApiKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) => proxyFetch(`api-keys/${id}/`, { method: "DELETE" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.apiKeys });
      qc.invalidateQueries({ queryKey: keys.apiKeyUsage });
    },
  });
}

/** Validate an API key against its provider. */
export function useValidateApiKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) =>
      proxyFetch(`api-keys/${id}/validate/`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.apiKeys });
    },
  });
}

/** Set an API key as the user's default. */
export function useSetDefaultApiKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) =>
      proxyFetch(`api-keys/${id}/set-default/`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.apiKeys });
    },
  });
}

/** Deactivate an API key. */
export function useDeactivateApiKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) =>
      proxyFetch(`api-keys/${id}/deactivate/`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.apiKeys });
    },
  });
}