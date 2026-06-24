// lib/api-client.js  (used by "use client" components)
// Thin wrapper over the BFF proxy. Redirects to /login on 401.

export async function apiClient(path, options = {}) {
  const res = await fetch(`/api/proxy/${path.replace(/^\//, "")}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });

  if (res.status === 401 && typeof window !== "undefined") {
    window.location.href = "/login";
    return null;
  }
  return res;
}