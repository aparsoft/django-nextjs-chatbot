// app/api/proxy/[...path]/route.js
import { cookies } from "next/headers";
import { djangoUrl } from "@/lib/django";
import { getValidAccessToken } from "@/lib/server-auth";

const BODY_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

async function handler(request, ctx) {
  const { path = [] } = await ctx.params; // Next.js 16: params is async
  const cookieStore = await cookies();

  const access = await getValidAccessToken(cookieStore);
  if (!access)
    return Response.json({ error: "Not authenticated" }, { status: 401 });

  const search = new URL(request.url).search;
  const target = djangoUrl(`/${path.join("/")}/`) + search;

  const init = {
    method: request.method,
    headers: { Authorization: `Bearer ${access}` },
    cache: "no-store",
  };

  const contentType = request.headers.get("content-type");
  if (BODY_METHODS.has(request.method)) {
    if (contentType) init.headers["Content-Type"] = contentType;
    init.body = await request.text();
  }

  const djangoRes = await fetch(target, init);

  const body = await djangoRes.arrayBuffer();
  return new Response(body, {
    status: djangoRes.status,
    headers: {
      "Content-Type":
        djangoRes.headers.get("content-type") ?? "application/json",
    },
  });
}

export {
  handler as GET,
  handler as POST,
  handler as PUT,
  handler as PATCH,
  handler as DELETE,
};