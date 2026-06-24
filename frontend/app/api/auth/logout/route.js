// app/api/auth/logout/route.js
import { cookies } from "next/headers";
import { djangoUrl, ENDPOINTS } from "@/lib/django";
import { REFRESH_TOKEN_COOKIE, clearAuthCookies } from "@/lib/cookies";

export async function POST() {
  const cookieStore = await cookies();
  const refresh = cookieStore.get(REFRESH_TOKEN_COOKIE)?.value;

  if (refresh) {
    try {
      await fetch(djangoUrl(ENDPOINTS.logout), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh }),
        cache: "no-store",
      });
    } catch {
      // Network error — still clear local cookies below.
    }
  }

  clearAuthCookies(cookieStore);
  return Response.json({ ok: true }, { status: 200 });
}