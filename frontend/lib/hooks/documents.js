// lib/hooks/documents.js
// TanStack Query hooks for document CRUD, upload, processing, and stats.
// All calls go through the BFF proxy.

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { keys } from "@/lib/query-keys";

/**
 * Shared proxy fetch for JSON endpoints.
 * Parses JSON, throws a decorated Error on non-2xx so React Query
 * surfaces `error.status` and `error.data` to callers.
 */
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
 * Upload a document via multipart/form-data.
 * The BFF proxy passes the raw body through, so we must NOT set
 * Content-Type manually — the browser sets the correct boundary.
 */
async function proxyUpload(path, formData) {
  const res = await fetch(`/api/proxy/chatbot/${path.replace(/^\//, "")}`, {
    method: "POST",
    body: formData,
    // Intentionally no Content-Type header — browser sets multipart boundary.
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

/** List documents with optional query filters. */
export function useDocuments(params = "") {
  return useQuery({
    queryKey: [...keys.documents, params],
    queryFn: () => proxyFetch(`documents/${params}`),
    staleTime: 30_000,
  });
}

/** Single document detail. */
export function useDocument(id) {
  return useQuery({
    queryKey: keys.document(id),
    queryFn: () => proxyFetch(`documents/${id}/`),
    enabled: !!id,
  });
}

/**
 * Upload a new document (multipart/form-data).
 * Invalidates the documents list and storage stats on success.
 */
export function useUploadDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ file, title, chat_session, tags }) => {
      const formData = new FormData();
      formData.append("file", file);
      if (title) formData.append("title", title);
      if (chat_session) formData.append("chat_session", chat_session);
      if (tags) formData.append("tags", tags);
      return proxyUpload("documents/", formData);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.documents });
      qc.invalidateQueries({ queryKey: keys.storageStats });
      qc.invalidateQueries({ queryKey: keys.processingStats });
    },
  });
}

/** Trigger processing for a document. */
export function useProcessDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) =>
      proxyFetch(`documents/${id}/process/`, { method: "POST" }),
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: keys.document(id) });
      qc.invalidateQueries({ queryKey: keys.documentStatus(id) });
      qc.invalidateQueries({ queryKey: keys.processingStats });
    },
  });
}

/** Retry processing for a failed document. */
export function useRetryDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) =>
      proxyFetch(`documents/${id}/retry/`, { method: "POST" }),
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: keys.document(id) });
      qc.invalidateQueries({ queryKey: keys.documentStatus(id) });
      qc.invalidateQueries({ queryKey: keys.processingStats });
    },
  });
}

/** Update a document's metadata (title, description, tags). */
export function useUpdateDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }) =>
      proxyFetch(`documents/${id}/`, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    onSuccess: (data, { id }) => {
      qc.setQueryData(keys.document(id), data);
      qc.invalidateQueries({ queryKey: keys.documents });
    },
  });
}

/** Delete a document. */
export function useDeleteDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) =>
      proxyFetch(`documents/${id}/`, { method: "DELETE" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.documents });
      qc.invalidateQueries({ queryKey: keys.storageStats });
      qc.invalidateQueries({ queryKey: keys.processingStats });
    },
  });
}

/**
 * Poll a document's processing status.
 * Refetches every 2s while the status is `pending` or `processing`,
 * stops automatically once `completed` or `failed`.
 */
export function useDocumentStatus(id) {
  return useQuery({
    queryKey: keys.documentStatus(id),
    queryFn: () => proxyFetch(`documents/${id}/status/`),
    enabled: !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.processing_status;
      if (status === "pending" || status === "processing") return 2000;
      return false;
    },
  });
}

/** Storage dashboard stats. */
export function useStorageStats() {
  return useQuery({
    queryKey: keys.storageStats,
    queryFn: () => proxyFetch("documents/storage-stats/"),
    staleTime: 60_000,
  });
}

/** Processing pipeline stats. */
export function useProcessingStats() {
  return useQuery({
    queryKey: keys.processingStats,
    queryFn: () => proxyFetch("documents/processing-stats/"),
    staleTime: 30_000,
  });
}