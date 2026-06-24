// tests/refresh.test.js
import { describe, it, expect, vi, beforeEach } from "vitest";
import { refreshTokens } from "@/lib/refresh";

describe("refreshTokens — concurrency collapsing", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("collapses concurrent callers sharing a refresh token into ONE Django call", async () => {
    const fetchSpy = vi
      .spyOn(global, "fetch")
      .mockResolvedValue(
        new Response(JSON.stringify({ access: "new-a", refresh: "new-r" }), {
          status: 200,
        }),
      );

    // Fire 5 refreshes with the SAME token, simultaneously.
    const results = await Promise.all(
      Array.from({ length: 5 }, () => refreshTokens("same-refresh-token")),
    );

    expect(fetchSpy).toHaveBeenCalledTimes(1); // ← the whole point
    for (const r of results) {
      expect(r).toEqual({ access: "new-a", refresh: "new-r" });
    }
  });

  it("does NOT collapse different users (different refresh tokens)", async () => {
    const fetchSpy = vi
      .spyOn(global, "fetch")
      .mockResolvedValue(
        new Response(JSON.stringify({ access: "a", refresh: "r" }), {
          status: 200,
        }),
      );

    await Promise.all([
      refreshTokens("user-a-token"),
      refreshTokens("user-b-token"),
    ]);

    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });

  it("throws on 401 from Django", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Token is invalid" }), {
        status: 401,
      }),
    );

    await expect(refreshTokens("dead-token")).rejects.toThrow();
    await expect(refreshTokens("dead-token")).rejects.toHaveProperty(
      "status",
      401,
    );
  });

  it("keeps the old refresh token if backend did not rotate", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ access: "new-a" }), { status: 200 }),
    );

    const result = await refreshTokens("old-refresh");
    expect(result.access).toBe("new-a");
    expect(result.refresh).toBe("old-refresh"); // kept the old one
  });

  it("handles wrapped response shape { data: { tokens: {…} } }", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          data: { tokens: { access: "wrapped-a", refresh: "wrapped-r" } },
        }),
        { status: 200 },
      ),
    );

    const result = await refreshTokens("some-token");
    expect(result).toEqual({ access: "wrapped-a", refresh: "wrapped-r" });
  });

  it("allows sequential calls (lock is released after completion)", async () => {
    const fetchSpy = vi
      .spyOn(global, "fetch")
      .mockResolvedValue(
        new Response(JSON.stringify({ access: "a", refresh: "r" }), {
          status: 200,
        }),
      );

    await refreshTokens("token-1");
    await refreshTokens("token-1"); // same token, sequential → 2 calls

    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });
});