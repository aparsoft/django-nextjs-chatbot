"""
Serializers for UserPreference model.

Follows the operation-based serializer split pattern:
  - UserPreferenceSerializer        → read (list / retrieve)
  - UserPreferenceListSerializer    → lightweight read for list actions
  - UserPreferenceCreateSerializer  → POST create
  - UserPreferenceUpdateSerializer  → PATCH / PUT update

UserPreference has a OneToOneField to User, so there is typically
only one record per user. The create serializer is provided for
first-time setup; updates are the common path.
"""

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from ...models import UserPreference


# ---------------------------------------------------------------------------
#  Read Serializers
# ---------------------------------------------------------------------------


class UserPreferenceSerializer(serializers.ModelSerializer):
    """Read serializer for UserPreference (retrieve).

    Includes all user-facing fields plus computed properties
    like has_usage_limits, is_dark_mode, and is_light_mode.
    """

    has_usage_limits = serializers.BooleanField(read_only=True)
    is_dark_mode = serializers.BooleanField(read_only=True)
    is_light_mode = serializers.BooleanField(read_only=True)
    user_email = serializers.SerializerMethodField()

    class Meta:
        model = UserPreference
        fields = [
            "id",
            "user",
            "user_email",
            "default_model",
            "default_temperature",
            "default_max_tokens",
            "enable_auto_summarization",
            "summarization_trigger_tokens",
            "max_summary_tokens",
            "summarization_style",
            "custom_system_prompt",
            "use_custom_system_prompt",
            "response_language",
            "enable_streaming",
            "enable_code_execution",
            "daily_message_limit",
            "daily_token_limit",
            "theme",
            "show_token_count",
            "enable_notifications",
            "save_conversation_history",
            "allow_data_training",
            "additional_settings",
            "has_usage_limits",
            "is_dark_mode",
            "is_light_mode",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "created_at",
            "updated_at",
        ]

    @extend_schema_field(serializers.EmailField(allow_null=True))
    def get_user_email(self, obj) -> str | None:
        return obj.user.email if obj.user else None


class UserPreferenceListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list actions.

    Shows the most relevant preference fields without the full
    detail of custom prompts and additional_settings.
    """

    has_usage_limits = serializers.BooleanField(read_only=True)
    user_email = serializers.SerializerMethodField()

    class Meta:
        model = UserPreference
        fields = [
            "id",
            "user",
            "user_email",
            "default_model",
            "default_temperature",
            "summarization_style",
            "response_language",
            "enable_streaming",
            "theme",
            "has_usage_limits",
            "daily_message_limit",
            "daily_token_limit",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.EmailField(allow_null=True))
    def get_user_email(self, obj) -> str | None:
        return obj.user.email if obj.user else None


# ---------------------------------------------------------------------------
#  Write Serializers
# ---------------------------------------------------------------------------


class UserPreferenceCreateSerializer(serializers.ModelSerializer):
    """Create serializer for UserPreference.

    Only accepts fields the user should set at creation time.
    The `user` field is injected by the view from request.user.
    Most fields have sensible defaults defined on the model.
    """

    class Meta:
        model = UserPreference
        fields = [
            "default_model",
            "default_temperature",
            "default_max_tokens",
            "enable_auto_summarization",
            "summarization_trigger_tokens",
            "max_summary_tokens",
            "summarization_style",
            "custom_system_prompt",
            "use_custom_system_prompt",
            "response_language",
            "enable_streaming",
            "enable_code_execution",
            "daily_message_limit",
            "daily_token_limit",
            "theme",
            "show_token_count",
            "enable_notifications",
            "save_conversation_history",
            "allow_data_training",
            "additional_settings",
        ]

    def validate_default_temperature(self, value):
        """Ensure temperature is within the valid range (0.0–2.0)."""
        if not (0.0 <= value <= 2.0):
            raise serializers.ValidationError(
                "Temperature must be between 0.0 and 2.0."
            )
        return value

    def validate_default_max_tokens(self, value):
        """Ensure max tokens is a positive integer."""
        if value < 1:
            raise serializers.ValidationError(
                "Max tokens must be at least 1."
            )
        return value

    def validate_summarization_trigger_tokens(self, value):
        """Ensure summarization trigger tokens is a positive integer."""
        if value < 1:
            raise serializers.ValidationError(
                "Summarization trigger tokens must be at least 1."
            )
        return value

    def validate_max_summary_tokens(self, value):
        """Ensure max summary tokens is a positive integer."""
        if value < 1:
            raise serializers.ValidationError(
                "Max summary tokens must be at least 1."
            )
        return value


class UserPreferenceUpdateSerializer(serializers.ModelSerializer):
    """Update serializer for UserPreference — all fields optional.

    Supports partial updates (PATCH). Only preference fields are
    writable; the user relationship cannot be changed.
    """

    class Meta:
        model = UserPreference
        fields = [
            "default_model",
            "default_temperature",
            "default_max_tokens",
            "enable_auto_summarization",
            "summarization_trigger_tokens",
            "max_summary_tokens",
            "summarization_style",
            "custom_system_prompt",
            "use_custom_system_prompt",
            "response_language",
            "enable_streaming",
            "enable_code_execution",
            "daily_message_limit",
            "daily_token_limit",
            "theme",
            "show_token_count",
            "enable_notifications",
            "save_conversation_history",
            "allow_data_training",
            "additional_settings",
        ]
        extra_kwargs = {field: {"required": False} for field in fields}

    def validate_default_temperature(self, value):
        """Ensure temperature is within the valid range (0.0–2.0)."""
        if not (0.0 <= value <= 2.0):
            raise serializers.ValidationError(
                "Temperature must be between 0.0 and 2.0."
            )
        return value

    def validate_default_max_tokens(self, value):
        """Ensure max tokens is a positive integer."""
        if value < 1:
            raise serializers.ValidationError(
                "Max tokens must be at least 1."
            )
        return value

    def validate_summarization_trigger_tokens(self, value):
        """Ensure summarization trigger tokens is a positive integer."""
        if value < 1:
            raise serializers.ValidationError(
                "Summarization trigger tokens must be at least 1."
            )
        return value

    def validate_max_summary_tokens(self, value):
        """Ensure max summary tokens is a positive integer."""
        if value < 1:
            raise serializers.ValidationError(
                "Max summary tokens must be at least 1."
            )
        return value
