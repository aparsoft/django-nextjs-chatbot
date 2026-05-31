"""
Serializers for UserAPIKey model.

Follows the operation-based serializer split pattern:
  - UserAPIKeySerializer        → read (list / retrieve)
  - UserAPIKeyListSerializer    → lightweight read for list actions
  - UserAPIKeyCreateSerializer  → POST create
  - UserAPIKeyUpdateSerializer  → PATCH / PUT update

The encrypted key is NEVER exposed through the API — only the
masked display_key is included in read responses.
"""

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from ...models import UserAPIKey


# ---------------------------------------------------------------------------
#  Read Serializers
# ---------------------------------------------------------------------------


class UserAPIKeySerializer(serializers.ModelSerializer):
    """Read serializer for UserAPIKey (list / retrieve).

    Includes all user-facing fields plus computed properties
    like display_key, provider_name, and has_limits.
    The raw key is never exposed.
    """

    display_key = serializers.CharField(read_only=True)
    provider_name = serializers.CharField(read_only=True)
    has_limits = serializers.BooleanField(read_only=True)
    user_email = serializers.SerializerMethodField()

    class Meta:
        model = UserAPIKey
        fields = [
            "id",
            "user",
            "user_email",
            "provider",
            "provider_name",
            "provider_display_name",
            "key_name",
            "display_key",
            "is_active",
            "is_default",
            "is_validated",
            "last_validated_at",
            "validation_error",
            "usage_count",
            "last_used_at",
            "total_tokens_used",
            "daily_limit",
            "monthly_limit",
            "has_limits",
            "custom_config",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "key_prefix",
            "encrypted_key",
            "is_validated",
            "last_validated_at",
            "validation_error",
            "usage_count",
            "last_used_at",
            "total_tokens_used",
            "created_at",
            "updated_at",
        ]

    @extend_schema_field(serializers.EmailField(allow_null=True))
    def get_user_email(self, obj) -> str | None:
        return obj.user.email if obj.user else None


class UserAPIKeyListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list actions.

    Omits heavy fields (custom_config, validation_error) to keep
    list responses small and fast.
    """

    display_key = serializers.CharField(read_only=True)
    provider_name = serializers.CharField(read_only=True)
    has_limits = serializers.BooleanField(read_only=True)
    user_email = serializers.SerializerMethodField()

    class Meta:
        model = UserAPIKey
        fields = [
            "id",
            "user",
            "user_email",
            "provider",
            "provider_name",
            "key_name",
            "display_key",
            "is_active",
            "is_default",
            "is_validated",
            "usage_count",
            "total_tokens_used",
            "has_limits",
            "created_at",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.EmailField(allow_null=True))
    def get_user_email(self, obj) -> str | None:
        return obj.user.email if obj.user else None


# ---------------------------------------------------------------------------
#  Write Serializers
# ---------------------------------------------------------------------------


class UserAPIKeyCreateSerializer(serializers.ModelSerializer):
    """Create serializer for UserAPIKey.

    Accepts the raw API key string which will be encrypted
    before storage. The `user` field is injected by the view
    from request.user.
    """

    api_key = serializers.CharField(
        write_only=True,
        help_text="Raw API key (encrypted before storage)",
    )

    class Meta:
        model = UserAPIKey
        fields = [
            "provider",
            "provider_display_name",
            "key_name",
            "api_key",
            "is_default",
            "daily_limit",
            "monthly_limit",
            "custom_config",
        ]

    def validate_api_key(self, value):
        """Ensure api_key is not empty and has a reasonable length."""
        if not value or not value.strip():
            raise serializers.ValidationError("API key cannot be empty.")
        if len(value.strip()) < 8:
            raise serializers.ValidationError(
                "API key appears too short — please check and try again."
            )
        return value.strip()

    def validate_key_name(self, value):
        """Ensure key_name is not empty."""
        if not value or not value.strip():
            raise serializers.ValidationError("Key name cannot be empty.")
        return value.strip()

    def validate_daily_limit(self, value):
        """Ensure daily_limit is a positive integer if provided."""
        if value is not None and value < 1:
            raise serializers.ValidationError(
                "Daily limit must be a positive integer."
            )
        return value

    def validate_monthly_limit(self, value):
        """Ensure monthly_limit is a positive integer if provided."""
        if value is not None and value < 1:
            raise serializers.ValidationError(
                "Monthly limit must be a positive integer."
            )
        return value

    def create(self, validated_data):
        """Encrypt the API key before saving."""
        api_key = validated_data.pop("api_key")
        instance = super().create(validated_data)
        instance.encrypt_api_key(api_key)
        instance.save()
        return instance


class UserAPIKeyUpdateSerializer(serializers.ModelSerializer):
    """Update serializer for UserAPIKey — all fields optional.

    Supports partial updates (PATCH). The encrypted key and usage
    tracking fields are not writable here — use rotate_key() or
    increment_usage() on the model.
    """

    api_key = serializers.CharField(
        write_only=True,
        required=False,
        help_text="New raw API key (re-encrypts on save)",
    )

    class Meta:
        model = UserAPIKey
        fields = [
            "provider",
            "provider_display_name",
            "key_name",
            "api_key",
            "is_active",
            "is_default",
            "daily_limit",
            "monthly_limit",
            "custom_config",
        ]
        extra_kwargs = {
            field: {"required": False}
            for field in [
                "provider",
                "provider_display_name",
                "key_name",
                "is_active",
                "is_default",
                "daily_limit",
                "monthly_limit",
                "custom_config",
            ]
        }

    def validate_key_name(self, value):
        """Ensure key_name is not empty if provided."""
        if value is not None and not value.strip():
            raise serializers.ValidationError("Key name cannot be empty.")
        return value.strip() if value else value

    def validate_api_key(self, value):
        """Ensure api_key is valid if provided."""
        if value is not None:
            if not value.strip():
                raise serializers.ValidationError("API key cannot be empty.")
            if len(value.strip()) < 8:
                raise serializers.ValidationError(
                    "API key appears too short — please check and try again."
                )
        return value.strip() if value else value

    def validate_daily_limit(self, value):
        """Ensure daily_limit is a positive integer if provided."""
        if value is not None and value < 1:
            raise serializers.ValidationError(
                "Daily limit must be a positive integer."
            )
        return value

    def validate_monthly_limit(self, value):
        """Ensure monthly_limit is a positive integer if provided."""
        if value is not None and value < 1:
            raise serializers.ValidationError(
                "Monthly limit must be a positive integer."
            )
        return value

    def update(self, instance, validated_data):
        """Handle API key rotation if a new key is provided."""
        api_key = validated_data.pop("api_key", None)
        instance = super().update(instance, validated_data)
        if api_key:
            instance.rotate_key(api_key)
        return instance
