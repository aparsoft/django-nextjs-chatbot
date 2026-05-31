# accounts/api/serializers/response_serializers.py

"""
Response Serializers for OpenAPI Schema Generation

Typed serializers for views that construct response dicts manually.
These are used with @extend_schema(responses=...) to produce accurate
OpenAPI documentation.
"""

from rest_framework import serializers


# ---------------------------------------------------------------------------
#  Generic envelope serializers
# ---------------------------------------------------------------------------


class ErrorResponseSerializer(serializers.Serializer):
    """Standard error envelope."""

    message = serializers.CharField(help_text="Human-readable error description.")
    code = serializers.CharField(required=False, help_text="Machine-readable error code.")
    status = serializers.CharField(default="error")
    errors = serializers.DictField(required=False, help_text="Field-level errors.")


# ---------------------------------------------------------------------------
#  Auth — Login
# ---------------------------------------------------------------------------


class LoginRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()


class _TokenSerializer(serializers.Serializer):
    access = serializers.CharField(help_text="JWT access token.")
    refresh = serializers.CharField(help_text="JWT refresh token.")


class _LoginUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    full_name = serializers.CharField()
    role = serializers.CharField()
    status = serializers.CharField()
    email_verified = serializers.BooleanField()


class _ProfileCompletionSerializer(serializers.Serializer):
    is_complete = serializers.BooleanField()
    missing_fields = serializers.ListField(child=serializers.CharField())
    next_steps = serializers.ListField(child=serializers.CharField())


class _LoginUserExtendedSerializer(_LoginUserSerializer):
    profile_completion = _ProfileCompletionSerializer()


class _NavigationSerializer(serializers.Serializer):
    dashboard_route = serializers.CharField()
    next_action = serializers.CharField()


class _SessionInfoSerializer(serializers.Serializer):
    login_count = serializers.IntegerField()
    last_login = serializers.CharField(required=False, allow_null=True)


class _LoginDataSerializer(serializers.Serializer):
    tokens = _TokenSerializer()
    user = _LoginUserExtendedSerializer()
    navigation = _NavigationSerializer()
    session_info = _SessionInfoSerializer()


class LoginResponseSerializer(serializers.Serializer):
    """Successful login response."""

    message = serializers.CharField(default="Login successful")
    status = serializers.CharField(default="success")
    data = _LoginDataSerializer()


# ---------------------------------------------------------------------------
#  Auth — Logout
# ---------------------------------------------------------------------------


class LogoutRequestSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=False, help_text="JWT refresh token to blacklist.")
    refresh_token = serializers.CharField(required=False, help_text="Alternative key name.")
    all_devices = serializers.BooleanField(required=False, default=False)


class LogoutResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    code = serializers.CharField()
    status = serializers.CharField(default="success")


# ---------------------------------------------------------------------------
#  Auth — Registration
# ---------------------------------------------------------------------------


class RegisterRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password1 = serializers.CharField(help_text="Password.")
    password2 = serializers.CharField(help_text="Confirm password.")
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    role = serializers.CharField(default="user", help_text="'user' or 'admin'.")
    username = serializers.CharField(required=False)


class _RegisterUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    username = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    role = serializers.CharField()
    email_verified = serializers.BooleanField()


class _RegisterTokensSerializer(serializers.Serializer):
    refresh = serializers.CharField()
    access = serializers.CharField()


class RegisterResponseSerializer(serializers.Serializer):
    """Successful registration response."""

    message = serializers.CharField()
    status = serializers.CharField(default="success")
    user = _RegisterUserSerializer()
    tokens = _RegisterTokensSerializer()
    next_steps = serializers.ListField(child=serializers.CharField())


# ---------------------------------------------------------------------------
#  Auth — CSRF
# ---------------------------------------------------------------------------


class CSRFResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    status = serializers.CharField()
    csrfToken = serializers.CharField()


# ---------------------------------------------------------------------------
#  Profile — Avatar
# ---------------------------------------------------------------------------


class AvatarResponseSerializer(serializers.Serializer):
    """Avatar get/upload response."""

    message = serializers.CharField()
    status = serializers.CharField()
    data = serializers.DictField(required=False)
    error_code = serializers.CharField(required=False)


class AvatarDeleteResponseSerializer(serializers.Serializer):
    """Avatar delete response."""

    message = serializers.CharField()
    status = serializers.CharField()
