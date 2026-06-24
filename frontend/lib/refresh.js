// lib/refresh.js
// Per-token in-flight collapsing — concurrent refreshes sharing a refresh token
// are collapsed onto a single Django request. Keyed by token so different users
// never share a promise.

import { djangoUrl, ENDPOINTS } from "@/lib/django";

const inFlight = new Map();

async function callDjangoRefresh(refreshToken) {
  const res = await fetch(djangoUrl(ENDPOINTS.refresh), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh: refreshToken }),
    cache: "no-store",
  });

  if (!res.ok) {
    const err = new Error("Token refresh failed");
    err.status = res.status;
    throw err;
  }

  const data = await res.json().catch(() => ({}));
  // Tolerate both flat SimpleJWT shape and a wrapped { data: { tokens } } shape.
  const tokens = data?.data?.tokens ?? data;
  return {
    access: tokens.access,
    refresh: tokens.refresh ?? refreshToken,
  };
}

/**
 * Refresh tokens, collapsing concurrent callers that share the same refresh token
 * onto a single Django request. Returns { access, refresh }. Throws on failure.
 */
export function refreshTokens(refreshToken) {
  if (inFlight.has(refreshToken)) return inFlight.get(refreshToken);
  const promise = callDjangoRefresh(refreshToken).finally(() =>
    inFlight.delete(refreshToken),
  );
  inFlight.set(refreshToken, promise);
  return promise;
}