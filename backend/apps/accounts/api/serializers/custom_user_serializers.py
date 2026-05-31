# accounts/api/serializers/custom_user_serializers.py

"""
Serializers for CustomUser and UserContact models.

Follows the operation-based serializer split pattern:
  - <Model>Serializer        → read (list / retrieve)
  - <Model>CreateSerializer   → POST create
  - <Model>UpdateSerializer   → PATCH / PUT update
"""

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from accounts.models.custom_user import UserContact
from core.models import Country

CustomUser = get_user_model()


# ---------------------------------------------------------------------------
#  UserContact
# ---------------------------------------------------------------------------


class UserContactSerializer(serializers.ModelSerializer):
    """Read serializer for UserContact."""

    country_name = serializers.SerializerMethodField()

    class Meta:
        model = UserContact
        fields = [
            "id",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "country",
            "country_name",
            "contact_info",
            "timezone",
            "availability",
        ]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_country_name(self, obj) -> str | None:
        if obj.country:
            return obj.country.name
        return None


class UserContactCreateSerializer(serializers.ModelSerializer):
    """Create serializer for UserContact."""

    class Meta:
        model = UserContact
        fields = [
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "country",
            "contact_info",
            "timezone",
            "availability",
        ]


class UserContactUpdateSerializer(serializers.ModelSerializer):
    """Update serializer for UserContact — all fields optional."""

    class Meta:
        model = UserContact
        fields = [
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "country",
            "contact_info",
            "timezone",
            "availability",
        ]
        extra_kwargs = {
            field: {"required": False} for field in fields
        }


# ---------------------------------------------------------------------------
#  CustomUser
# ---------------------------------------------------------------------------


class CustomUserSerializer(serializers.ModelSerializer):
    """Read serializer for CustomUser (list / retrieve)."""

    full_name = serializers.CharField(source="get_full_name", read_only=True)
    contact = UserContactSerializer(read_only=True)

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "role",
            "profile_picture",
            "email_verified",
            "phone_verified",
            "two_factor_enabled",
            "last_password_change",
            "last_active",
            "login_count",
            "date_joined",
            "is_active",
            "contact",
        ]
        read_only_fields = [
            "id",
            "date_joined",
            "last_active",
            "login_count",
            "email_verified",
            "phone_verified",
            "last_password_change",
        ]


class CustomUserListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list actions."""

    full_name = serializers.CharField(source="get_full_name", read_only=True)

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "username",
            "email",
            "full_name",
            "role",
            "is_active",
            "email_verified",
        ]
        read_only_fields = fields


class CustomUserCreateSerializer(serializers.ModelSerializer):
    """Create serializer for CustomUser — password required."""

    password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
        help_text="Must meet system password requirements.",
    )

    class Meta:
        model = CustomUser
        fields = [
            "email",
            "username",
            "password",
            "first_name",
            "last_name",
            "role",
        ]

    def validate_email(self, value):
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = CustomUser(**validated_data)
        user.set_password(password)
        user.save()
        return user


class CustomUserUpdateSerializer(serializers.ModelSerializer):
    """Update serializer for CustomUser — all fields optional."""

    class Meta:
        model = CustomUser
        fields = [
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
        ]
        extra_kwargs = {
            field: {"required": False} for field in fields
        }

    def validate_email(self, value):
        if CustomUser.objects.filter(email=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value


# ---------------------------------------------------------------------------
#  Inline serializers for action responses
# ---------------------------------------------------------------------------


class PasswordChangeActionSerializer(serializers.Serializer):
    """Request body for the change-password action."""

    current_password = serializers.CharField(help_text="Current password for verification.")
    new_password = serializers.CharField(help_text="New password (min 8 chars).")
