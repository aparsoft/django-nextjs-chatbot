// app/api/auth/social/google/route.js
import { cookies } from "next/headers";
import { djangoUrl, ENDPOINTS } from "@/lib/django";
import { setAuthCookies } from "@/lib/cookies";

export async function POST(request) {
  const { id_token } = await request.json().catch(() => ({}));
  if (!id_token) {
    return Response.json({ error: "Google ID token is required" }, { status: 400 });
  }

  const res = await fetch(djangoUrl(ENDPOINTS.google), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_token }),
    cache: "no-store",
  });

  const payload = await res.json().catch(() => ({}));
  if (!res.ok) {
    return Response.json(
      { error: payload?.message || "Google authentication failed" },
      { status: res.status },
    );
  }

  const tokens = payload?.data?.tokens ?? payload?.tokens;
  const user = payload?.data?.user ?? payload?.user;
  if (!tokens?.access || !tokens?.refresh) {
    return Response.json({ error: "Malformed token response" }, { status: 502 });
  }

  const cookieStore = await cookies();
  setAuthCookies(cookieStore, tokens);
  return Response.json({ user }, { status: 200 });
}