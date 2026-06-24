// tests/auth-hooks.test.jsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import {
  useCurrentUser,
  useLogin,
  useLogout,
  useRegister,
  useGoogleLogin,
  authKeys,
} from "@/lib/auth-hooks";

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }) {
    return (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    );
  };
}

beforeEach(() => vi.restoreAllMocks());
afterEach(() => vi.unstubAllGlobals());

describe("useCurrentUser", () => {
  it("fetches the current user from /api/auth/me", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ user: { id: 1, email: "test@example.com" } }),
          { status: 200 },
        ),
      ),
    );

    const { result } = renderHook(() => useCurrentUser(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual({ id: 1, email: "test@example.com" });
    expect(fetch).toHaveBeenCalledWith(
      "/api/auth/me",
      expect.objectContaining({ headers: { "Content-Type": "application/json" } }),
    );
  });

  it("returns error state on 401", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ error: "Not authenticated" }), {
          status: 401,
        }),
      ),
    );

    const { result } = renderHook(() => useCurrentUser(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.data).toBeUndefined();
  });
});

describe("useLogin", () => {
  it("POSTs credentials to /api/auth/login and populates the user cache", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            user: { id: 1, email: "test@example.com" },
            navigation: { dashboard_route: "/dashboard" },
          }),
          { status: 200 },
        ),
      ),
    );

    const { result } = renderHook(() => useLogin(), {
      wrapper: createWrapper(),
    });

    await result.current.mutateAsync({ email: "test@example.com", password: "pw" });

    expect(fetch).toHaveBeenCalledWith(
      "/api/auth/login",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ email: "test@example.com", password: "pw" }),
      }),
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data.user).toEqual({ id: 1, email: "test@example.com" });
  });

  it("exposes the error on failed login", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ error: "Invalid email or password." }),
          { status: 401 },
        ),
      ),
    );

    const { result } = renderHook(() => useLogin(), {
      wrapper: createWrapper(),
    });

    try {
      await result.current.mutateAsync({ email: "x@y.com", password: "bad" });
    } catch {
      // expected
    }

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error.message).toBe("Invalid email or password.");
    expect(result.current.error.status).toBe(401);
  });
});

describe("useLogout", () => {
  it("POSTs to /api/auth/logout", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ ok: true }), { status: 200 }),
      ),
    );

    const { result } = renderHook(() => useLogout(), {
      wrapper: createWrapper(),
    });

    await result.current.mutateAsync();

    expect(fetch).toHaveBeenCalledWith(
      "/api/auth/logout",
      expect.objectContaining({ method: "POST" }),
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});

describe("useRegister", () => {
  it("POSTs registration data to /api/auth/register", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ user: { id: 2, email: "new@test.com" } }),
          { status: 201 },
        ),
      ),
    );

    const { result } = renderHook(() => useRegister(), {
      wrapper: createWrapper(),
    });

    const payload = {
      email: "new@test.com",
      password1: "Secure123!",
      password2: "Secure123!",
      first_name: "New",
      last_name: "User",
    };

    await result.current.mutateAsync(payload);

    expect(fetch).toHaveBeenCalledWith(
      "/api/auth/register",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(payload),
      }),
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data.user).toEqual({ id: 2, email: "new@test.com" });
  });
});

describe("useGoogleLogin", () => {
  it("POSTs the Google ID token to /api/auth/social/google", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ user: { id: 3, email: "g@gmail.com" } }),
          { status: 200 },
        ),
      ),
    );

    const { result } = renderHook(() => useGoogleLogin(), {
      wrapper: createWrapper(),
    });

    await result.current.mutateAsync({ id_token: "fake-google-token" });

    expect(fetch).toHaveBeenCalledWith(
      "/api/auth/social/google",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ id_token: "fake-google-token" }),
      }),
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data.user).toEqual({ id: 3, email: "g@gmail.com" });
  });

  it("exposes the error on invalid Google token", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ error: "Invalid Google token." }),
          { status: 401 },
        ),
      ),
    );

    const { result } = renderHook(() => useGoogleLogin(), {
      wrapper: createWrapper(),
    });

    try {
      await result.current.mutateAsync({ id_token: "bad" });
    } catch {
      // expected
    }

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error.message).toBe("Invalid Google token.");
  });
});

describe("authKeys", () => {
  it("exports the correct query key for the current user", () => {
    expect(authKeys.me).toEqual(["auth", "me"]);
  });
});