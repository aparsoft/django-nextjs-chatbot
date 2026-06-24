// lib/django.js
// The ONLY place Django URLs are defined. Route Handlers import from here.

// Server-side base (Docker/prod may differ from the browser base).
export const DJANGO_API =
  process.env.INTERNAL_API_URL ?? "http://localhost:8000/api/v1";

export const ENDPOINTS = {
  login: "/accounts/auth/login/",
  refresh: "/accounts/auth/refresh/",
  logout: "/accounts/auth/logout/",
  register: "/accounts/auth/register/",
  me: "/accounts/users/me/",
  google: "/accounts/auth/social/google/",
};

/** Build an absolute Django URL from a relative API path. */
export function djangoUrl(path) {
  const clean = path.startsWith("/") ? path : `/${path}`;
  return `${DJANGO_API}${clean}`;
}