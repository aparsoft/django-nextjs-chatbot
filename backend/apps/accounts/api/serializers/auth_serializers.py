# accounts/api/serializers/auth_serializers.py

"""
Authentication Serializers

Handles JWT token generation, user registration, and password management.
"""

from rest_framework import serializers
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
)
from rest_framework_simplejwt.exceptions import InvalidToken
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from django.utils.text import slugify
import logging
import uuid

logger = logging.getLogger(__name__)
User = get_user_model()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Enhanced JWT token serializer that includes user profile data.
    """

    username_field = User.EMAIL_FIELD

    def validate(self, attrs):
        data = super().validate(attrs)

        role = self.user.role
        status_val = "active" if self.user.is_active else "inactive"

        user_data = {
            "id": self.user.id,
            "email": self.user.email,
            "first_name": self.user.first_name,
            "last_name": self.user.last_name,
            "full_name": self.user.full_name,
            "role": role,
            "status": status_val,
            "email_verified": self.user.email_verified,
        }

        data["user"] = user_data
        return data


class RegisterSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration.
    """

    role = serializers.CharField(
        default="user",
        help_text="User role: 'user' or 'admin'.",
    )
    password1 = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        help_text="Password must meet system requirements.",
    )
    password2 = serializers.CharField(
        write_only=True,
        required=True,
        help_text="Must match password1.",
    )
    email = serializers.EmailField(
        required=True,
        help_text="Primary email for the account.",
    )
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)
    username = serializers.CharField(
        required=False,
        help_text="Optional — auto-generated if omitted.",
    )

    class Meta:
        model = User
        fields = [
            "email",
            "first_name",
            "last_name",
            "username",
            "role",
            "password1",
            "password2",
        ]

    def validate(self, attrs):
        if attrs["password1"] != attrs["password2"]:
            raise serializers.ValidationError(
                {"password2": "Password fields didn't match."}
            )

        if User.objects.filter(email=attrs["email"]).exists():
            raise serializers.ValidationError(
                {"email": "This email address is already registered."}
            )

        role = attrs.get("role", "user")
        if role not in ["user", "admin"]:
            raise serializers.ValidationError(
                {"role": "Invalid role. Must be 'user' or 'admin'."}
            )

        return attrs

    def generate_unique_username(self, first_name, last_name):
        """Generate a unique username from the user's name."""
        first_name = "".join(e for e in first_name if e.isalnum())
        last_name = "".join(e for e in last_name if e.isalnum())
        base_username = slugify(f"{first_name} {last_name}") or "user"

        username = base_username
        for _ in range(10):
            if not User.objects.filter(username=username).exists():
                return username
            username = f"{base_username}{uuid.uuid4().hex[:6]}"

        return f"user_{uuid.uuid4().hex[:10]}"

    def create(self, validated_data):
        username = validated_data.get("username") or self.generate_unique_username(
            validated_data["first_name"], validated_data["last_name"]
        )

        password = validated_data.pop("password1")
        validated_data.pop("password2", None)
        validated_data.pop("username", None)
        role = validated_data.pop("role", "user")

        user = User(
            username=username,
            email=validated_data["email"],
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
            role=role,
            email_verified=False,
            last_active=timezone.now(),
            login_count=0,
        )
        user.set_password(password)
        user.save()

        logger.info(f"Created new {role} user: {user.email}")
        return user


class CustomTokenRefreshSerializer(TokenRefreshSerializer):
    """Token refresh serializer that reads the refresh token from cookies."""

    refresh = serializers.CharField(required=False)

    def validate(self, attrs):
        request = self.context["request"]
        refresh_token = request.COOKIES.get("refresh_token")

        if refresh_token:
            attrs["refresh"] = refresh_token

        if not attrs.get("refresh"):
            raise InvalidToken("No valid refresh token found")

        return super().validate(attrs)


class SocialAuthSerializer(serializers.Serializer):
    """Serializer for OAuth authentication."""

    provider = serializers.CharField(required=True)
    code = serializers.CharField(required=True)
    redirect_uri = serializers.CharField(required=True)


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer for password change."""

    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)
    new_password_confirm = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password": "Password fields didn't match."}
            )

        try:
            validate_password(attrs["new_password"])
        except DjangoValidationError as e:
            raise serializers.ValidationError({"new_password": list(e.messages)})

        return attrs
