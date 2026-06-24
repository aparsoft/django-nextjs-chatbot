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