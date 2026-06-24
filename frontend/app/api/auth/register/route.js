// app/api/auth/register/route.js
import { cookies } from "next/headers";
import { djangoUrl, ENDPOINTS } from "@/lib/django";
import { setAuthCookies } from "@/lib/cookies";

export async function POST(request) {
  const body = await request.json().catch(() => null);
  if (!body?.email || !body?.password1 || body.password1 !== body.password2) {
    return Response.json({ error: "Invalid registration data" }, { status: 400 });
  }

  const res = await fetch(djangoUrl(ENDPOINTS.register), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  const payload = await res.json().catch(() => ({}));

  if (!res.ok) {
    return Response.json(
      { error: payload?.message || "Registration failed", fields: payload },
      { status: res.status },
    );
  }

  const tokens = payload?.tokens ?? payload?.data?.tokens;
  if (tokens?.access && tokens?.refresh) {
    const cookieStore = await cookies();
    setAuthCookies(cookieStore, tokens);
  }
  return Response.json(
    { user: payload?.user ?? payload?.data?.user },
    { status: 201 },
  );
}