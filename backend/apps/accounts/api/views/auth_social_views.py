"""Google OAuth authentication views — ID-token verification flow.

Verifies a Google ID token server-side using the official ``google-auth`` library,
then mints our own SimpleJWT pair so the rest of the system never special-cases
social users.  See backend/docs/AUTHENTICATION.md §9 for the full design.
"""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.services.cookies import set_auth_cookies

logger = logging.getLogger(__name__)
User = get_user_model()


class GoogleAuthSerializer(serializers.Serializer):
    """Validate the incoming Google ID token payload."""

    id_token = serializers.CharField(
        required=True,
        help_text="Google ID token (JWT) obtained from Google Identity Services.",
    )


class GoogleLoginView(APIView):
    """Verify a Google ID token and issue our own SimpleJWT pair.

    Flow:
      1. Browser obtains a Google ID token via Google Identity Services.
      2. BFF forwards ``{ "id_token": "…" }`` to this endpoint.
      3. ``google-auth`` verifies the token signature + audience (our client_id).
      4. ``get_or_create`` a CustomUser by the verified email.
      5. Mint our own access/refresh tokens and set httpOnly cookies.

    The response shape matches password login: ``{ data: { tokens, user } }``.
    """

    permission_classes = [AllowAny]
    throttle_scope = "login"

    @transaction.atomic
    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        id_token_str = serializer.validated_data["id_token"]

        # 1. Verify the ID token against Google's public keys + our client_id (audience).
        try:
            from google.oauth2 import id_token as google_id_token
            from google.auth.transport import requests as google_requests

            claims = google_id_token.verify_oauth2_token(
                id_token_str,
                google_requests.Request(),
                settings.GOOGLE_OAUTH_CLIENT_ID,
            )
        except ValueError:
            logger.warning("Google ID token verification failed")
            return Response(
                {
                    "message": "Invalid Google token.",
                    "code": "invalid_google_token",
                    "status": "error",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except Exception:
            logger.error(
                "Unexpected error during Google token verification", exc_info=True
            )
            return Response(
                {
                    "message": "An error occurred during Google authentication.",
                    "code": "server_error",
                    "status": "error",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # 2. Require email_verified — never trust an unverified Google email.
        if not claims.get("email_verified"):
            return Response(
                {
                    "message": "Google account email is not verified.",
                    "code": "email_unverified",
                    "status": "error",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        email = claims["email"].lower()
        given_name = claims.get("given_name", "")
        family_name = claims.get("family_name", "")
        google_sub = claims.get("sub", "")

        # 3. get_or_create — OAuth users are normal users with an unusable password.
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "username": email.split("@")[0],
                "first_name": given_name,
                "last_name": family_name,
                "email_verified": True,
            },
        )
        if created:
            user.set_unusable_password()
            user.role = "user"
            user.save(update_fields=["password", "role"])

        # 4. Record the linked provider (idempotent).
        providers = user.social_auth_providers or {
            "active_providers": [],
            "connections": {},
            "default_login": None,
        }
        if "google" not in providers.get("active_providers", []):
            providers.setdefault("active_providers", []).append("google")
        providers.setdefault("connections", {})["google"] = {"sub": google_sub}
        user.social_auth_providers = providers

        # 5. Update login bookkeeping.
        user.login_count += 1
        user.update_last_active(save=False)
        user.save()

        # 6. Mint OUR tokens — identical shape to password login.
        refresh = RefreshToken.for_user(user)
        access = str(refresh.access_token)

        response = Response(
            {
                "message": "Login successful",
                "status": "success",
                "data": {
                    "tokens": {
                        "access": access,
                        "refresh": str(refresh),
                    },
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "full_name": user.full_name,
                        "role": user.role,
                        "email_verified": user.email_verified,
                    },
                    "created": created,
                },
            },
            status=status.HTTP_200_OK,
        )

        # 7. Set httpOnly cookies (same as password login).
        set_auth_cookies(response, access=access, refresh=str(refresh))

        logger.info(
            "Google login: %s (created=%s, sub=%s)", user.email, created, google_sub
        )
        return response
