// lib/auth-hooks.js
// TanStack Query hooks for authentication — used by client components.
// All hooks call the BFF route handlers (/api/auth/...), never Django directly.

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

// ── Query keys ──────────────────────────────────────────────────────────────
export const authKeys = {
  me: ["auth", "me"],
};

// ── Fetch helpers ────────────────────────────────────────────────────────────
async function fetchJSON(url, options) {
  const res = await fetch(url, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options?.headers || {}) },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data?.error || data?.message || data?.detail || "Request failed");
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

// ── useCurrentUser ───────────────────────────────────────────────────────────
/** Fetch the current user via the BFF /api/auth/me endpoint. */
export function useCurrentUser() {
  return useQuery({
    queryKey: authKeys.me,
    queryFn: () => fetchJSON("/api/auth/me").then((d) => d.user),
    retry: false,
    staleTime: 1000 * 60, // 1 min — user data doesn't change often
  });
}

// ── useLogin ─────────────────────────────────────────────────────────────────
/** Login mutation — POSTs to /api/auth/login, invalidates the user query. */
export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ email, password }) =>
      fetchJSON("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      }),
    onSuccess: (data) => {
      queryClient.setQueryData(authKeys.me, data.user);
    },
    onError: () => {
      queryClient.setQueryData(authKeys.me, null);
    },
  });
}

// ── useRegister ──────────────────────────────────────────────────────────────
/** Register mutation — POSTs to /api/auth/register. */
export function useRegister() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload) =>
      fetchJSON("/api/auth/register", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: (data) => {
      queryClient.setQueryData(authKeys.me, data.user);
    },
  });
}

// ── useLogout ────────────────────────────────────────────────────────────────
/** Logout mutation — POSTs to /api/auth/logout, clears the user cache. */
export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => fetchJSON("/api/auth/logout", { method: "POST" }),
    onSuccess: () => {
      queryClient.setQueryData(authKeys.me, null);
      queryClient.invalidateQueries({ queryKey: authKeys.me });
    },
  });
}

// ── useGoogleLogin ────────────────────────────────────────────────────────────
/** Google OAuth mutation — POSTs the Google ID token to /api/auth/social/google. */
export function useGoogleLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id_token }) =>
      fetchJSON("/api/auth/social/google", {
        method: "POST",
        body: JSON.stringify({ id_token }),
      }),
    onSuccess: (data) => {
      queryClient.setQueryData(authKeys.me, data.user);
    },
  });
}