"""Centralised auth-cookie helpers — the single source of truth for cookie lifetimes.

All auth views (login, refresh, Google OAuth, logout) must use these helpers
instead of calling ``response.set_cookie`` directly.  This guarantees the cookie
``max_age`` always mirrors the SimpleJWT token lifetimes defined in ``SIMPLE_JWT``
settings, eliminating the class of bugs where one view hardcodes a different
lifetime than another.

Usage::

    from accounts.services.cookies import set_auth_cookies, clear_auth_cookies

    response = Response(data, status=200)
    set_auth_cookies(response, access=access_token, refresh=refresh_token)
    return response
"""

from django.conf import settings


def _cookie_opts():
    """Return the base cookie options shared by all auth cookies."""
    sj = settings.SIMPLE_JWT
    return {
        "httponly": sj.get("AUTH_COOKIE_HTTP_ONLY", True),
        "secure": sj.get("AUTH_COOKIE_SECURE", not settings.DEBUG),
        "samesite": sj.get("AUTH_COOKIE_SAMESITE", "Lax"),
        "path": "/",
    }


def set_auth_cookies(response, *, access=None, refresh=None):
    """Write access, refresh, and auth_state cookies onto *response*.

    Lifetimes are read from ``SIMPLE_JWT`` so they always match the JWT lifetimes.

    :param response: a DRF ``Response`` (or Django ``HttpResponse``)
    :param access: the access token string (or ``None`` to skip)
    :param refresh: the refresh token string (or ``None`` to skip)
    """
    sj = settings.SIMPLE_JWT
    opts = _cookie_opts()

    if access is not None:
        response.set_cookie(
            sj.get("AUTH_COOKIE", "access_token"),
            access,
            max_age=sj.get("AUTH_COOKIE_ACCESS_MAX_AGE", 300),
            **opts,
        )

    if refresh is not None:
        response.set_cookie(
            sj.get("AUTH_COOKIE_REFRESH", "refresh_token"),
            refresh,
            max_age=sj.get("AUTH_COOKIE_REFRESH_MAX_AGE", 86400),
            **opts,
        )

    # Non-httpOnly flag so the frontend can cheaply detect "logged in" state
    # without a round-trip to /api/auth/me.
    response.set_cookie(
        "auth_state",
        "authenticated",
        max_age=sj.get("AUTH_COOKIE_REFRESH_MAX_AGE", 86400),
        httponly=False,
        secure=opts["secure"],
        samesite=opts["samesite"],
        path=opts["path"],
    )


def clear_auth_cookies(response):
    """Remove all auth-related cookies from *response*.

    Called on logout and on failed refresh.  Always clears every cookie even
    if the Django blacklist call failed — a network blip must not trap the user.
    """
    for name in ("auth_state", "access_token", "refresh_token", "csrftoken"):
        response.delete_cookie(name, path="/")