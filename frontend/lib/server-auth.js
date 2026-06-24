// lib/server-auth.js  (server-only — reads/writes cookies)
import {
  ACCESS_TOKEN_COOKIE,
  REFRESH_TOKEN_COOKIE,
  setAuthCookies,
  clearAuthCookies,
} from "@/lib/cookies";
import { isExpired } from "@/lib/jwt";
import { refreshTokens } from "@/lib/refresh";

/**
 * Return a usable access token, refreshing if the current one is expired.
 * Rotated cookies are written as a side effect. Returns null if the session is dead.
 *
 * ⚠️ This writes cookies — only call from Route Handlers or Server Actions.
 * For Server Components (layouts/pages), use `getValidAccessTokenReadOnly` instead.
 *
 * `cookieStore` must be the awaited result of cookies().
 */
export async function getValidAccessToken(cookieStore) {
  const access = cookieStore.get(ACCESS_TOKEN_COOKIE)?.value;
  if (access && !isExpired(access)) return access;

  const refresh = cookieStore.get(REFRESH_TOKEN_COOKIE)?.value;
  if (!refresh) return null;

  try {
    const tokens = await refreshTokens(refresh);
    setAuthCookies(cookieStore, tokens);
    return tokens.access;
  } catch {
    clearAuthCookies(cookieStore);
    return null;
  }
}

/**
 * Read-only version for Server Components (layouts, pages).
 *
 * Server Components CANNOT modify cookies (Next.js 16 throws a runtime error).
 * This function reads the access token and refreshes it if expired, but does
 * NOT write the rotated cookies back — it just returns the fresh access token.
 *
 * If the session is dead (no refresh token or refresh fails), returns null
 * so the caller can `redirect("/auth/login")`.
 *
 * The rotated cookies will be persisted by the next Route Handler call
 * (e.g. /api/auth/me or /api/proxy/...) which CAN write cookies.
 *
 * `cookieStore` must be the awaited result of cookies().
 */
export async function getValidAccessTokenReadOnly(cookieStore) {
    const access = cookieStore.get(ACCESS_TOKEN_COOKIE)?.value;
    if (access && !isExpired(access)) return access;

    const refresh = cookieStore.get(REFRESH_TOKEN_COOKIE)?.value;
    if (!refresh) return null;

    try {
        const tokens = await refreshTokens(refresh);
        // Return the fresh token WITHOUT writing cookies — Server Components
        // cannot modify cookies. The next Route Handler call will persist them.
        return tokens.access;
    } catch {
        // Session is dead — return null so the caller redirects to login.
        // Cookie cleanup happens via the /api/auth/logout Route Handler.
        return null;
    }
}