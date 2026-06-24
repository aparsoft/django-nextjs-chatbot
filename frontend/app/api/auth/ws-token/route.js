// app/api/auth/ws-token/route.js
import { cookies } from "next/headers";
import { getValidAccessToken } from "@/lib/server-auth";

export async function GET() {
  const cookieStore = await cookies();
  const token = await getValidAccessToken(cookieStore);
  if (!token) return Response.json({ error: "Not authenticated" }, { status: 401 });
  return Response.json({ token }, { status: 200 });
}