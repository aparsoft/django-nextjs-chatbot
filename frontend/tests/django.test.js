// tests/django.test.js
import { describe, it, expect } from "vitest";
import { djangoUrl, ENDPOINTS, DJANGO_API } from "@/lib/django";

describe("djangoUrl", () => {
  it("builds an absolute URL from a relative path with leading slash", () => {
    expect(djangoUrl("/accounts/auth/login/")).toBe(
      `${DJANGO_API}/accounts/auth/login/`,
    );
  });

  it("builds an absolute URL from a relative path without leading slash", () => {
    expect(djangoUrl("accounts/auth/login/")).toBe(
      `${DJANGO_API}/accounts/auth/login/`,
    );
  });
});

describe("ENDPOINTS", () => {
  it("contains all required auth endpoints", () => {
    expect(ENDPOINTS.login).toBe("/accounts/auth/login/");
    expect(ENDPOINTS.refresh).toBe("/accounts/auth/refresh/");
    expect(ENDPOINTS.logout).toBe("/accounts/auth/logout/");
    expect(ENDPOINTS.register).toBe("/accounts/auth/register/");
    expect(ENDPOINTS.me).toBe("/accounts/users/me/");
    expect(ENDPOINTS.google).toBe("/accounts/auth/social/google/");
  });
});