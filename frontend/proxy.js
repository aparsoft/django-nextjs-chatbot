// proxy.js  (Next.js 16 — replaces the deprecated middleware.js)
//
// In Next.js 16, `middleware.js` is deprecated and renamed to `proxy.js`.
// The exported function must be named `proxy` (or use a default export).
// The logic, matcher config, and NextResponse API are identical.
//
// This is the first line of defense — a bouncer that checks if you have a ticket.
// It does NOT validate the token (that happens server-side in route handlers/layouts).

import { NextResponse } from "next/server";
import { ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE } from "@/lib/cookies";

export function proxy(request) {
  // A session "exists" if either cookie is present. The access cookie may have
  // expired (max-age 5m) while the refresh cookie is still valid — don't kick the
  // user out in that case; the proxy/layout will refresh server-side.
  const hasSession =
    request.cookies.get(ACCESS_TOKEN_COOKIE) ||
    request.cookies.get(REFRESH_TOKEN_COOKIE);

  if (!hasSession) {
    const loginUrl = new URL("/auth/login", request.url);
    loginUrl.searchParams.set("callbackUrl", request.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  // Run on everything EXCEPT public pages, ALL /api routes (they handle their own
  // auth and must return JSON, not an HTML redirect), and static assets.
  matcher: [
    "/((?!auth|api|_next/static|_next/image|favicon.ico|public).*)",
  ],
};