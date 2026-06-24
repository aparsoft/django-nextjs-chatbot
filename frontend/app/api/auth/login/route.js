// app/api/auth/login/route.js
import { cookies } from "next/headers";
import { djangoUrl, ENDPOINTS } from "@/lib/django";
import { setAuthCookies } from "@/lib/cookies";

export async function POST(request) {
  let body;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const { email, password } = body ?? {};
  if (!email || !password) {
    return Response.json(
      { error: "Email and password are required" },
      { status: 400 },
    );
  }

  const djangoRes = await fetch(djangoUrl(ENDPOINTS.login), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
    cache: "no-store",
  });

  const payload = await djangoRes.json().catch(() => ({}));

  if (!djangoRes.ok) {
    const message = payload?.message || payload?.detail || "Invalid credentials";
    return Response.json({ error: message }, { status: djangoRes.status });
  }

  const tokens = payload?.data?.tokens ?? payload?.tokens;
  const user = payload?.data?.user ?? payload?.user;
  const navigation = payload?.data?.navigation ?? null;

  if (!tokens?.access || !tokens?.refresh) {
    return Response.json(
      { error: "Malformed token response from server" },
      { status: 502 },
    );
  }

  const cookieStore = await cookies();
  setAuthCookies(cookieStore, tokens);

  return Response.json({ user, navigation }, { status: 200 });
}