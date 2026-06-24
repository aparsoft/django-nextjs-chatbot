// tests/cookies.test.js
import { describe, it, expect } from "vitest";
import {
  ACCESS_TOKEN_COOKIE,
  REFRESH_TOKEN_COOKIE,
  ACCESS_MAX_AGE,
  REFRESH_MAX_AGE,
  setAuthCookies,
  clearAuthCookies,
} from "@/lib/cookies";

function mockCookieStore() {
  const store = new Map();
  return {
    get: (k) => (store.has(k) ? { value: store.get(k) } : undefined),
    set: (k, v, opts) => store.set(k, { value: v, opts }),
    _store: store,
  };
}

describe("cookie constants", () => {
  it("exports the correct cookie names", () => {
    expect(ACCESS_TOKEN_COOKIE).toBe("access_token");
    expect(REFRESH_TOKEN_COOKIE).toBe("refresh_token");
  });

  it("exports max-ages that match Django SIMPLE_JWT", () => {
    expect(ACCESS_MAX_AGE).toBe(300); // 5 minutes
    expect(REFRESH_MAX_AGE).toBe(86400); // 1 day
  });
});

describe("setAuthCookies", () => {
  it("sets both cookies with the correct max-ages", () => {
    const cs = mockCookieStore();
    setAuthCookies(cs, { access: "a-token", refresh: "r-token" });

    expect(cs._store.get(ACCESS_TOKEN_COOKIE).value).toBe("a-token");
    expect(cs._store.get(ACCESS_TOKEN_COOKIE).opts.maxAge).toBe(300);
    expect(cs._store.get(REFRESH_TOKEN_COOKIE).value).toBe("r-token");
    expect(cs._store.get(REFRESH_TOKEN_COOKIE).opts.maxAge).toBe(86400);
  });

  it("sets httpOnly on both cookies", () => {
    const cs = mockCookieStore();
    setAuthCookies(cs, { access: "a", refresh: "r" });

    expect(cs._store.get(ACCESS_TOKEN_COOKIE).opts.httpOnly).toBe(true);
    expect(cs._store.get(REFRESH_TOKEN_COOKIE).opts.httpOnly).toBe(true);
  });

  it("sets path to /", () => {
    const cs = mockCookieStore();
    setAuthCookies(cs, { access: "a", refresh: "r" });

    expect(cs._store.get(ACCESS_TOKEN_COOKIE).opts.path).toBe("/");
    expect(cs._store.get(REFRESH_TOKEN_COOKIE).opts.path).toBe("/");
  });

  it("skips access cookie if access is falsy", () => {
    const cs = mockCookieStore();
    setAuthCookies(cs, { access: null, refresh: "r" });

    expect(cs._store.has(ACCESS_TOKEN_COOKIE)).toBe(false);
    expect(cs._store.get(REFRESH_TOKEN_COOKIE).value).toBe("r");
  });

  it("skips refresh cookie if refresh is falsy", () => {
    const cs = mockCookieStore();
    setAuthCookies(cs, { access: "a", refresh: null });

    expect(cs._store.get(ACCESS_TOKEN_COOKIE).value).toBe("a");
    expect(cs._store.has(REFRESH_TOKEN_COOKIE)).toBe(false);
  });
});

describe("clearAuthCookies", () => {
  it("sets both cookies to empty with maxAge 0", () => {
    const cs = mockCookieStore();
    clearAuthCookies(cs);

    expect(cs._store.get(ACCESS_TOKEN_COOKIE).value).toBe("");
    expect(cs._store.get(ACCESS_TOKEN_COOKIE).opts.maxAge).toBe(0);
    expect(cs._store.get(REFRESH_TOKEN_COOKIE).value).toBe("");
    expect(cs._store.get(REFRESH_TOKEN_COOKIE).opts.maxAge).toBe(0);
  });
});