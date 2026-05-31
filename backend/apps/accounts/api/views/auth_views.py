# accounts/api/views/auth_views.py

"""
Authentication Views — Login & Logout

Provides JWT-based authentication with login and logout endpoints.
"""

from rest_framework import status
from rest_framework.response import Response
from django.utils import timezone
from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
import logging
from typing import Dict, Any

from drf_spectacular.utils import extend_schema, extend_schema_view

from ..serializers import CustomTokenObtainPairSerializer
from ..serializers.response_serializers import (
    LoginRequestSerializer,
    LoginResponseSerializer,
    ErrorResponseSerializer,
    LogoutRequestSerializer,
    LogoutResponseSerializer,
)
from ...models import CustomUser, UserContact

logger = logging.getLogger(__name__)
User = get_user_model()


@extend_schema_view(
    post=extend_schema(
        tags=["Authentication"],
        summary="Login",
        description="Authenticate with email/password and receive JWT tokens.",
        request=LoginRequestSerializer,
        responses={200: LoginResponseSerializer, 401: ErrorResponseSerializer, 400: ErrorResponseSerializer},
    )
)
@method_decorator([ensure_csrf_cookie], name="dispatch")
class CustomTokenObtainPairView(TokenObtainPairView):
    """
    JWT login endpoint.

    Authenticates a user and returns access/refresh tokens along with
    user profile data.
    """

    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        # Request validation
        if not request.data.get("email") or not request.data.get("password"):
            return Response(
                {
                    "message": "Email and password are required.",
                    "code": "required_fields_missing",
                    "status": "error",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Pre-validate user exists and is active
        try:
            user = User.objects.get(email=request.data.get("email"))
            if not user.is_active:
                return Response(
                    {
                        "message": "Account is inactive. Please contact support.",
                        "code": "account_inactive",
                        "status": "error",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
        except User.DoesNotExist:
            pass  # Don't reveal that the user doesn't exist

        try:
            serializer = self.get_serializer(data=request.data)

            if not serializer.is_valid():
                errors = serializer.errors
                if "non_field_errors" in errors:
                    return Response(
                        {
                            "message": "Authentication failed. Please check your credentials.",
                            "code": "authentication_failed",
                            "status": "error",
                        },
                        status=status.HTTP_401_UNAUTHORIZED,
                    )
                return Response(
                    {
                        "message": "Login validation failed",
                        "code": "validation_error",
                        "status": "error",
                        "errors": errors,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            data = serializer.validated_data
            user = serializer.user

            # Update user's login count and last active
            user.login_count += 1
            user.last_active = timezone.now()
            user.save(update_fields=["login_count", "last_active"])

            # Build response
            enhanced_data = self._build_login_response(user, data)
            response = Response(
                {
                    "message": "Login successful",
                    "status": "success",
                    "data": enhanced_data,
                },
                status=status.HTTP_200_OK,
            )

            # Set secure HTTP-only cookies
            self._set_auth_cookies(response, data)

            logger.info(f"Successful login: {user.email} (role={user.role})")
            return response

        except AuthenticationFailed:
            return Response(
                {
                    "message": "Invalid email or password.",
                    "code": "invalid_credentials",
                    "status": "error",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        except Exception as e:
            logger.error("Unexpected login error:", exc_info=True)
            return Response(
                {
                    "message": "An error occurred during login. Please try again.",
                    "code": "server_error",
                    "status": "error",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _build_login_response(
        self, user: CustomUser, token_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build the login response payload with user data and navigation."""
        user_data = token_data.get("user", {})

        # Check profile completion
        profile_completion = self._check_profile_completion(user)

        # Determine dashboard route
        if user.role == "admin":
            dashboard_route = "/platform/admin"
        else:
            dashboard_route = "/dashboard"

        return {
            "tokens": {
                "access": token_data["access"],
                "refresh": token_data["refresh"],
            },
            "user": {
                **user_data,
                "profile_completion": profile_completion,
            },
            "navigation": {
                "dashboard_route": dashboard_route,
                "next_action": self._get_next_action(user),
            },
            "session_info": {
                "login_count": user.login_count,
                "last_login": (
                    user.last_login.isoformat() if user.last_login else None
                ),
            },
        }

    def _set_auth_cookies(self, response: Response, token_data: Dict[str, Any]) -> None:
        """Set secure HTTP-only authentication cookies."""
        cookie_settings = {
            "httponly": True,
            "samesite": "Lax",
            "secure": not settings.DEBUG,
            "path": "/",
        }

        response.set_cookie(
            "refresh_token",
            token_data["refresh"],
            max_age=7 * 24 * 60 * 60,
            **cookie_settings,
        )
        response.set_cookie(
            "access_token", token_data["access"], max_age=60 * 60, **cookie_settings
        )
        response.set_cookie(
            "auth_state",
            "authenticated",
            httponly=False,
            max_age=7 * 24 * 60 * 60,
            **{k: v for k, v in cookie_settings.items() if k != "httponly"},
        )

    def _check_profile_completion(self, user: CustomUser) -> Dict[str, Any]:
        """Check if user profile is complete and what steps are needed."""
        completion_status = {
            "is_complete": True,
            "missing_fields": [],
            "next_steps": [],
        }

        if not user.first_name or not user.last_name:
            completion_status["is_complete"] = False
            completion_status["missing_fields"].append("name")
            completion_status["next_steps"].append("Complete your name")

        if not user.email_verified:
            completion_status["is_complete"] = False
            completion_status["missing_fields"].append("email_verification")
            completion_status["next_steps"].append("Verify your email address")

        try:
            contact = user.contact
            if not contact.country or not contact.city:
                completion_status["is_complete"] = False
                completion_status["missing_fields"].append("location")
                completion_status["next_steps"].append("Add your location")
        except UserContact.DoesNotExist:
            completion_status["is_complete"] = False
            completion_status["missing_fields"].append("contact")
            completion_status["next_steps"].append("Complete contact information")

        return completion_status

    def _get_next_action(self, user: CustomUser) -> str:
        """Determine the next recommended action for the user."""
        if not user.email_verified:
            return "verify_email"
        if user.role == "admin":
            return "system_overview"
        return "complete_profile"


@extend_schema_view(
    post=extend_schema(
        tags=["Authentication"],
        summary="Logout",
        description="Blacklist the refresh token and clear auth cookies.",
        request=LogoutRequestSerializer,
        responses={200: LogoutResponseSerializer},
    )
)
class LogoutView(APIView):
    """
    Logout endpoint.

    Blacklists the provided refresh token and clears all auth cookies.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh") or request.data.get(
                "refresh_token"
            )
            all_devices = request.data.get("all_devices", False)

            # Handle logout without valid auth
            if request.auth is None and request.user is None:
                return self._create_logout_response(
                    message="Session expired, cookies cleared",
                    code="logout_expired_token",
                )

            # Handle logout without refresh token
            if not refresh_token:
                if hasattr(request, "user") and request.user.is_authenticated:
                    request.user.update_last_active()
                return self._create_logout_response(
                    message="Logged out successfully", code="logout_without_token"
                )

            try:
                token = RefreshToken(refresh_token)

                # Verify token belongs to current user
                if (
                    hasattr(request, "user")
                    and request.user.is_authenticated
                    and token.payload.get("user_id") != request.user.id
                ):
                    return self._create_logout_response(
                        message="Invalid token, but logged out", code="token_mismatch"
                    )

                token.blacklist()

                if hasattr(request, "user") and request.user.is_authenticated:
                    request.user.update_last_active()

                # Multi-device logout
                if all_devices and hasattr(request, "user") and request.user.is_authenticated:
                    logger.info(f"Logging out all devices for user: {request.user.id}")
                    OutstandingToken.objects.filter(user=request.user).delete()

                return self._create_logout_response(
                    message="Successfully logged out", code="logout_success"
                )

            except Exception:
                return self._create_logout_response(
                    message="Invalid token, but logged out", code="invalid_token"
                )

        except Exception as e:
            logger.error(f"Unexpected logout error: {str(e)}", exc_info=True)
            return self._create_logout_response(
                message="Error occurred, but logged out", code="error_but_logged_out"
            )

    def _create_logout_response(self, message: str, code: str) -> Response:
        """Create logout response with cookie cleanup."""
        response = Response(
            {"message": message, "code": code, "status": "success"},
            status=status.HTTP_200_OK,
        )
        for cookie in ["auth_state", "access_token", "refresh_token", "csrftoken"]:
            response.delete_cookie(cookie, path="/")
        return response
