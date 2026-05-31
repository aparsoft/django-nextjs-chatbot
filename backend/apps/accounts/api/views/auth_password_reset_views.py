# accounts/api/views/auth_password_reset_views.py

"""
Authentication Views — Password Management

Provides password reset, confirmation, change, and email verification endpoints.
"""

from rest_framework import status, serializers as sz
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_str, force_bytes
import logging
from rest_framework.throttling import AnonRateThrottle
from decouple import config

from drf_spectacular.utils import extend_schema, extend_schema_view

from ..serializers.response_serializers import ErrorResponseSerializer

logger = logging.getLogger(__name__)
User = get_user_model()


# ---------- Inline request serializers for schema generation ----------

class PasswordResetRequestSerializer(sz.Serializer):
    email = sz.EmailField(help_text="Email address to send reset instructions to.")


class PasswordResetConfirmRequestSerializer(sz.Serializer):
    uid = sz.CharField(help_text="Base64-encoded user ID from the reset link.")
    token = sz.CharField(help_text="Reset token from the reset link.")
    new_password = sz.CharField(help_text="New password (min 8 characters).")
    confirm_password = sz.CharField(help_text="Must match new_password.")


class PasswordChangeRequestSerializer(sz.Serializer):
    current_password = sz.CharField(help_text="Current password for verification.")
    new_password = sz.CharField(help_text="New password (min 8 characters).")


class EmailVerifyQuerySerializer(sz.Serializer):
    uid = sz.CharField(required=False, help_text="Base64-encoded user ID.")
    token = sz.CharField(required=False, help_text="Email verification token.")


class MessageResponseSerializer(sz.Serializer):
    message = sz.CharField()
    status = sz.CharField()


class TokenValidationResponseSerializer(sz.Serializer):
    message = sz.CharField()
    status = sz.CharField()
    valid = sz.BooleanField()
    user_email = sz.EmailField(required=False)


# ---------- Views ----------

@extend_schema_view(
    post=extend_schema(
        tags=["Authentication"],
        summary="Request Password Reset",
        description="Request a password reset email for the given address.",
        request=PasswordResetRequestSerializer,
        responses={200: MessageResponseSerializer, 400: ErrorResponseSerializer},
    )
)
class PasswordResetView(APIView):
    """Request a password reset."""

    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]

    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response(
                {
                    "message": "Email address is required",
                    "code": "email_required",
                    "status": "error",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email=email)
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))

            domain = config("DOMAIN_NAME", "localhost")
            frontend_url = (
                "http://localhost:3000" if domain == "localhost" else f"https://{domain}"
            )
            reset_url = f"{frontend_url}/auth/reset-password?uid={uid}&token={token}"

            # TODO: Send email with reset_url via Celery task
            logger.info(f"Password reset requested for: {email}")

            return Response(
                {"message": "Password reset instructions sent to your email", "status": "success"},
                status=status.HTTP_200_OK,
            )

        except User.DoesNotExist:
            # Security: don't reveal whether email exists
            return Response(
                {"message": "If an account exists, reset instructions will be sent", "status": "success"},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Password reset error for {email}: {str(e)}", exc_info=True)
            return Response(
                {"message": "Error processing request", "code": "server_error", "status": "error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema_view(
    post=extend_schema(
        tags=["Authentication"],
        summary="Confirm Password Reset",
        description="Set a new password using the token from the reset email.",
        request=PasswordResetConfirmRequestSerializer,
        responses={200: MessageResponseSerializer, 400: ErrorResponseSerializer},
    ),
    get=extend_schema(
        tags=["Authentication"],
        summary="Validate Reset Token",
        description="Check if a password reset token is valid without resetting.",
        parameters=[EmailVerifyQuerySerializer],
        responses={200: TokenValidationResponseSerializer, 400: ErrorResponseSerializer},
    )
)
class PasswordResetConfirmView(APIView):
    """Confirm password reset or validate the reset token."""

    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]

    def post(self, request):
        uid = request.data.get("uid")
        token = request.data.get("token")
        new_password = request.data.get("new_password")
        confirm_password = request.data.get("confirm_password")

        if not all([uid, token, new_password, confirm_password]):
            return Response(
                {"message": "Missing required fields", "code": "missing_fields", "status": "error"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_password != confirm_password:
            return Response(
                {"message": "Passwords do not match", "code": "password_mismatch", "status": "error"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(new_password) < 8:
            return Response(
                {"message": "Password must be at least 8 characters", "code": "password_too_short", "status": "error"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            try:
                user_id = force_str(urlsafe_base64_decode(uid))
                user = User.objects.get(pk=user_id)
            except (TypeError, ValueError, OverflowError, User.DoesNotExist):
                return Response(
                    {"message": "Invalid reset link", "code": "invalid_link", "status": "error"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not default_token_generator.check_token(user, token):
                return Response(
                    {"message": "Invalid or expired reset link", "code": "invalid_token", "status": "error"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user.set_password(new_password)
            user.save()
            logger.info(f"Password reset successful for: {user.email}")
            return Response({"message": "Password reset successful", "status": "success"}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Password reset confirmation error: {str(e)}", exc_info=True)
            return Response(
                {"message": "Error resetting password", "code": "server_error", "status": "error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def get(self, request):
        """Validate reset token without resetting password."""
        uid = request.GET.get("uid")
        token = request.GET.get("token")

        if not uid or not token:
            return Response(
                {"message": "Missing reset parameters", "code": "missing_params", "status": "error", "valid": False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            try:
                user_id = force_str(urlsafe_base64_decode(uid))
                user = User.objects.get(pk=user_id)
            except (TypeError, ValueError, OverflowError, User.DoesNotExist):
                return Response(
                    {"message": "Invalid reset link", "code": "invalid_link", "status": "error", "valid": False},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            is_valid = default_token_generator.check_token(user, token)
            return Response(
                {
                    "message": "Token validated" if is_valid else "Invalid or expired token",
                    "status": "success" if is_valid else "error",
                    "valid": is_valid,
                    "user_email": user.email if is_valid else None,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Token validation error: {str(e)}", exc_info=True)
            return Response(
                {"message": "Error validating token", "code": "server_error", "status": "error", "valid": False},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema_view(
    post=extend_schema(
        tags=["Authentication"],
        summary="Change Password",
        description="Change password for the currently authenticated user.",
        request=PasswordChangeRequestSerializer,
        responses={200: MessageResponseSerializer, 400: ErrorResponseSerializer},
    )
)
class PasswordChangeView(APIView):
    """Change password for authenticated users."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        current_password = request.data.get("current_password")
        new_password = request.data.get("new_password")

        if not current_password or not new_password:
            return Response(
                {
                    "message": "Current password and new password are required",
                    "code": "missing_fields",
                    "status": "error",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        if not user.check_password(current_password):
            return Response(
                {"message": "Current password is incorrect", "code": "invalid_current_password", "status": "error"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(new_password) < 8:
            return Response(
                {"message": "New password must be at least 8 characters", "code": "password_too_short", "status": "error"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if current_password == new_password:
            return Response(
                {"message": "New password must be different", "code": "same_password", "status": "error"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user.set_password(new_password)
            user.save()
            logger.info(f"Password changed for: {user.email}")
            return Response({"message": "Password changed successfully", "status": "success"}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Password change error: {str(e)}", exc_info=True)
            return Response(
                {"message": "Error changing password", "code": "server_error", "status": "error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema_view(
    post=extend_schema(
        tags=["Authentication"],
        summary="Request Email Verification",
        description="Send an email verification link to the authenticated user's address.",
        responses={200: MessageResponseSerializer, 500: ErrorResponseSerializer},
    ),
    get=extend_schema(
        tags=["Authentication"],
        summary="Verify Email",
        description="Verify email using the token from the verification link.",
        parameters=[EmailVerifyQuerySerializer],
        responses={200: MessageResponseSerializer, 400: ErrorResponseSerializer},
    )
)
class EmailVerificationView(APIView):
    """Email verification request and confirmation."""

    permission_classes = [AllowAny]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return [AllowAny()]

    def post(self, request):
        """Request email verification."""
        try:
            user = request.user

            if user.email_verified:
                return Response({"message": "Email is already verified", "status": "info"}, status=status.HTTP_200_OK)

            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))

            domain = config("DOMAIN_NAME", "localhost")
            frontend_url = "http://localhost:3000" if domain == "localhost" else f"https://{domain}"
            verification_url = f"{frontend_url}/auth/verify-email?uid={uid}&token={token}"

            # TODO: Send email via Celery task
            logger.info(f"Email verification requested for: {user.email}")
            return Response({"message": "Verification email sent", "status": "success"}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Email verification request error: {str(e)}", exc_info=True)
            return Response(
                {"message": "Error sending verification email", "code": "server_error", "status": "error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def get(self, request):
        """Verify email with token."""
        token = request.GET.get("token")
        uid = request.GET.get("uid")

        if not token or not uid:
            return Response(
                {"message": "Verification token and uid are required", "code": "token_required", "status": "error"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            try:
                user_id = force_str(urlsafe_base64_decode(uid))
                user = User.objects.get(pk=user_id)
            except (TypeError, ValueError, OverflowError, User.DoesNotExist):
                return Response(
                    {"message": "Invalid verification link", "code": "invalid_link", "status": "error"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not default_token_generator.check_token(user, token):
                return Response(
                    {"message": "Invalid or expired verification link", "code": "invalid_token", "status": "error"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if user.email_verified:
                return Response({"message": "Email is already verified", "status": "success"}, status=status.HTTP_200_OK)

            user.email_verified = True
            user.save(update_fields=["email_verified"])
            logger.info(f"Email verified: {user.email}")
            return Response({"message": "Email verified successfully", "status": "success"}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Email verification error: {str(e)}", exc_info=True)
            return Response(
                {"message": "Error verifying email", "code": "server_error", "status": "error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
