// lib/api.js  (server-only — used by Server Components)
import { cookies } from "next/headers";
import { djangoUrl } from "@/lib/django";
import { getValidAccessTokenReadOnly } from "@/lib/server-auth";

/**
 * Fetch a Django API path from the server with auth handled.
 * Returns parsed JSON. Throws (with `.status`) on non-OK.
 *
 * Uses the read-only token getter because Server Components
 * cannot modify cookies (Next.js 16 restriction).
 */
export async function apiFetch(path, options = {}) {
    const cookieStore = await cookies();
    const access = await getValidAccessTokenReadOnly(cookieStore);
    if (!access) {
        const err = new Error("UNAUTHENTICATED");
        err.status = 401;
        throw err;
    }

    const res = await fetch(djangoUrl(path), {
        ...options,
        headers: {
            Authorization: `Bearer ${access}`,
            "Content-Type": "application/json",
            ...(options.headers || {}),
        },
        cache: "no-store",
    });

    if (!res.ok) {
        const err = new Error(`API ${res.status} for ${path}`);
        err.status = res.status;
        throw err;
    }
    return res.json();
}