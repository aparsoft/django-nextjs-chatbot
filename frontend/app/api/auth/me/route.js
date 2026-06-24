// app/api/auth/me/route.js
import { cookies } from "next/headers";
import { djangoUrl, ENDPOINTS } from "@/lib/django";
import { getValidAccessToken } from "@/lib/server-auth";

export async function GET() {
  const cookieStore = await cookies();
  const access = await getValidAccessToken(cookieStore);
  if (!access) return Response.json({ error: "Not authenticated" }, { status: 401 });

  const res = await fetch(djangoUrl(ENDPOINTS.me), {
    headers: { Authorization: `Bearer ${access}` },
    cache: "no-store",
  });

  if (!res.ok)
    return Response.json({ error: "Failed to load user" }, { status: res.status });

  const user = await res.json();
  return Response.json({ user }, { status: 200 });
}