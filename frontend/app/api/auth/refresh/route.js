// app/api/auth/refresh/route.js
import { cookies } from "next/headers";
import { REFRESH_TOKEN_COOKIE, setAuthCookies, clearAuthCookies } from "@/lib/cookies";
import { refreshTokens } from "@/lib/refresh";

export async function POST() {
  const cookieStore = await cookies();
  const refreshToken = cookieStore.get(REFRESH_TOKEN_COOKIE)?.value;

  if (!refreshToken) {
    return Response.json({ error: "No refresh token" }, { status: 401 });
  }

  try {
    const tokens = await refreshTokens(refreshToken);
    setAuthCookies(cookieStore, tokens);
    return Response.json({ ok: true }, { status: 200 });
  } catch {
    clearAuthCookies(cookieStore);
    return Response.json({ error: "Session expired" }, { status: 401 });
  }
}