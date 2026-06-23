# backend/apps/accounts/services/auth.py

from rest_framework_simplejwt.authentication import JWTAuthentication
from django.conf import settings
from rest_framework.authentication import CSRFCheck
from rest_framework import exceptions


class CustomJWTCookieAuthentication(JWTAuthentication):
    """
    Custom authentication class that validates JWT tokens from cookies.
    Supports both cookie-based and header-based authentication.
    """

    def authenticate(self, request):
        # First try to get the token from the cookie
        header = self.get_header(request)

        if header is None:
            # Try to get token from cookies
            auth_cookie_name = settings.SIMPLE_JWT.get('AUTH_COOKIE', 'access_token')
            access_token = request.COOKIES.get(auth_cookie_name)
            if access_token:
                raw_token = access_token
            else:
                return None
        else:
            # Get token from Authorization header
            raw_token = self.get_raw_token(header)
            if raw_token is None:
                return None

        validated_token = self.get_validated_token(raw_token)
        user = self.get_user(validated_token)

        # Update last_active timestamp
        user.update_last_active(save=True)

        return user, validated_token

    def enforce_csrf(self, request):
        """
        Enforce CSRF validation for cookie-based authentication.
        """
        check = CSRFCheck()
        check.process_request(request)
        reason = check.process_view(request, None, (), {})
        if reason:
            raise exceptions.PermissionDenied('CSRF Failed: %s' % reason)
