// lib/cookies.js
// The ONLY place cookie names + options are defined.

export const ACCESS_TOKEN_COOKIE = "access_token";
export const REFRESH_TOKEN_COOKIE = "refresh_token";

// Mirror Django SIMPLE_JWT:
//   ACCESS_TOKEN_LIFETIME  = timedelta(minutes=5)
//   REFRESH_TOKEN_LIFETIME = timedelta(days=1)
export const ACCESS_MAX_AGE = 5 * 60; // 300s
export const REFRESH_MAX_AGE = 24 * 60 * 60; // 86400s

const isProd = process.env.NODE_ENV === "production";

/** Base options shared by both cookies. */
function baseOptions() {
  return {
    httpOnly: true, // JavaScript can never read these → XSS-safe
    secure: isProd, // HTTPS-only in production
    sameSite: "lax", // matches Django; "strict" can break OAuth-style redirects
    path: "/",
  };
}

/**
 * Write both auth cookies onto a resolved cookie store.
 * In Next.js 16 `cookies()` is async — pass the awaited store.
 */
export function setAuthCookies(cookieStore, { access, refresh }) {
  if (access) {
    cookieStore.set(ACCESS_TOKEN_COOKIE, access, {
      ...baseOptions(),
      maxAge: ACCESS_MAX_AGE,
    });
  }
  if (refresh) {
    cookieStore.set(REFRESH_TOKEN_COOKIE, refresh, {
      ...baseOptions(),
      maxAge: REFRESH_MAX_AGE,
    });
  }
}

/** Remove both auth cookies (logout / failed refresh). */
export function clearAuthCookies(cookieStore) {
  cookieStore.set(ACCESS_TOKEN_COOKIE, "", { ...baseOptions(), maxAge: 0 });
  cookieStore.set(REFRESH_TOKEN_COOKIE, "", { ...baseOptions(), maxAge: 0 });
}