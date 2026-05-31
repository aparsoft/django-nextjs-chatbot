# accounts/api/views/auth_register_views.py

"""
Authentication Views — Registration

Provides user registration and CSRF token endpoints.
"""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from django.db import transaction
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import JsonResponse
from django.conf import settings
import logging
from rest_framework.throttling import AnonRateThrottle

from drf_spectacular.utils import extend_schema, extend_schema_view

from ..serializers import RegisterSerializer
from ..serializers.response_serializers import (
    RegisterRequestSerializer,
    RegisterResponseSerializer,
    CSRFResponseSerializer,
    ErrorResponseSerializer,
)

logger = logging.getLogger(__name__)
User = get_user_model()

VALID_ROLES = ["user", "admin"]


@extend_schema_view(
    post=extend_schema(
        tags=["Authentication"],
        summary="Register",
        description="Create a new user account.",
        request=RegisterRequestSerializer,
        responses={201: RegisterResponseSerializer, 400: ErrorResponseSerializer},
    )
)
@method_decorator(ensure_csrf_cookie, name="dispatch")
class RegisterView(APIView):
    """User registration endpoint."""

    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        logger.info(f"Registration attempt for role: {request.data.get('role')}")

        try:
            # Validate required fields
            validation_result = self._validate_registration_data(request.data)
            if not validation_result["is_valid"]:
                return Response(
                    {
                        "message": validation_result["message"],
                        "code": validation_result["code"],
                        "status": "error",
                        "errors": validation_result.get("errors", {}),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            serializer = RegisterSerializer(
                data=request.data, context={"request": request}
            )

            if not serializer.is_valid():
                return Response(
                    {
                        "message": "Registration validation failed",
                        "code": "validation_error",
                        "status": "error",
                        "errors": serializer.errors,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user = serializer.save()
            refresh = RefreshToken.for_user(user)

            response_data = {
                "message": f"{user.role.title()} registration successful",
                "status": "success",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "role": user.role,
                    "email_verified": user.email_verified,
                },
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
                "next_steps": [
                    "Verify your email address",
                    "Complete your profile",
                    "Explore the platform",
                ],
            }

            logger.info(f"Successful registration: {user.email} (role={user.role})")
            return Response(response_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error("Registration error:", exc_info=True)
            return Response(
                {
                    "message": "An error occurred during registration. Please try again.",
                    "code": "server_error",
                    "status": "error",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _validate_registration_data(self, data: dict) -> dict:
        """Validate registration data."""
        required_fields = ["email", "password1", "password2", "first_name", "last_name"]
        missing_fields = [field for field in required_fields if not data.get(field)]

        if missing_fields:
            return {
                "is_valid": False,
                "message": f'Missing required fields: {", ".join(missing_fields)}',
                "code": "missing_required_fields",
                "errors": {field: ["This field is required."] for field in missing_fields},
            }

        # Validate role
        role = data.get("role", "user")
        if role not in VALID_ROLES:
            return {
                "is_valid": False,
                "message": f'Invalid role. Must be one of: {", ".join(VALID_ROLES)}',
                "code": "invalid_role",
            }

        # Email uniqueness
        if User.objects.filter(email=data.get("email")).exists():
            return {
                "is_valid": False,
                "message": "User with this email already exists",
                "code": "email_already_exists",
            }

        return {"is_valid": True}


@extend_schema_view(
    post=extend_schema(
        tags=["Authentication"],
        summary="Organization Register",
        description="Register a user associated with an organization.",
        request=RegisterRequestSerializer,
        responses={201: RegisterResponseSerializer, 400: ErrorResponseSerializer},
    )
)
@method_decorator(ensure_csrf_cookie, name="dispatch")
class OrganizationRegisterView(APIView):
    """Registration endpoint for organization-associated users."""

    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        try:
            serializer = RegisterSerializer(
                data=request.data, context={"request": request}
            )

            if not serializer.is_valid():
                return Response(
                    {
                        "message": "Validation failed",
                        "code": "validation_error",
                        "status": "error",
                        "errors": serializer.errors,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user = serializer.save()
            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    "message": "User created successfully",
                    "status": "success",
                    "data": {
                        "user": {
                            "id": user.id,
                            "email": user.email,
                            "name": user.full_name,
                            "role": user.role,
                        },
                        "tokens": {
                            "refresh": str(refresh),
                            "access": str(refresh.access_token),
                        },
                    },
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            logger.error("Organization registration error:", exc_info=True)
            return Response(
                {
                    "message": "Error creating user",
                    "code": "server_error",
                    "status": "error",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema_view(
    get=extend_schema(
        tags=["Authentication"],
        summary="Get CSRF Token",
        description="Retrieve a CSRF token cookie for use with subsequent requests.",
        responses={200: CSRFResponseSerializer},
    )
)
@method_decorator(ensure_csrf_cookie, name="dispatch")
class CSRFTokenView(APIView):
    """CSRF token endpoint."""

    permission_classes = [AllowAny]

    def get(self, request):
        from django.middleware.csrf import get_token

        csrf_token = get_token(request)
        response = JsonResponse(
            {
                "message": "CSRF cookie set successfully",
                "status": "success",
                "csrfToken": csrf_token,
            }
        )

        response["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"

        if settings.DEBUG:
            response["Access-Control-Allow-Origin"] = "http://localhost:3000"
            response["Access-Control-Allow-Credentials"] = "true"
            response["Access-Control-Allow-Headers"] = (
                "Content-Type, X-CSRFToken, Authorization"
            )

        return response
