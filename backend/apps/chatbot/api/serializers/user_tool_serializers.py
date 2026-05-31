"""
Serializers for UserTool model.

Follows the operation-based serializer split pattern:
  - UserToolSerializer        → read (list / retrieve)
  - UserToolListSerializer    → lightweight read for list actions
  - UserToolCreateSerializer  → POST create
  - UserToolUpdateSerializer  → PATCH / PUT update

Tools are defined in code (TOOL_REGISTRY) and users enable/disable
them with per-user configuration. Serializers handle validation and
representation only — business logic lives in the model.
"""

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from ...models import UserTool, TOOL_REGISTRY


# ---------------------------------------------------------------------------
#  Read Serializers
# ---------------------------------------------------------------------------


class UserToolSerializer(serializers.ModelSerializer):
    """Read serializer for UserTool (list / retrieve).

    Includes all user-facing fields plus the category display name.
    """

    user_email = serializers.SerializerMethodField()
    category_display = serializers.SerializerMethodField()

    class Meta:
        model = UserTool
        fields = [
            "id",
            "user",
            "user_email",
            "tool_name",
            "tool_display_name",
            "is_enabled",
            "configuration",
            "description",
            "category",
            "category_display",
            "icon",
            "usage_count",
            "last_used_at",
            "rate_limit",
            "rate_limit_period",
            "requires_approval",
            "is_approved",
            "approved_by",
            "approved_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "usage_count",
            "last_used_at",
            "is_approved",
            "approved_by",
            "approved_at",
            "created_at",
            "updated_at",
        ]

    @extend_schema_field(serializers.EmailField(allow_null=True))
    def get_user_email(self, obj) -> str | None:
        return obj.user.email if obj.user else None

    def get_category_display(self, obj) -> str:
        return obj.get_category_display()


class UserToolListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list actions.

    Omits verbose fields (configuration, approval details) to keep
    list responses small and fast.
    """

    user_email = serializers.SerializerMethodField()
    category_display = serializers.SerializerMethodField()

    class Meta:
        model = UserTool
        fields = [
            "id",
            "user",
            "user_email",
            "tool_name",
            "tool_display_name",
            "is_enabled",
            "description",
            "category",
            "category_display",
            "icon",
            "usage_count",
            "last_used_at",
            "is_approved",
            "created_at",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.EmailField(allow_null=True))
    def get_user_email(self, obj) -> str | None:
        return obj.user.email if obj.user else None

    def get_category_display(self, obj) -> str:
        return obj.get_category_display()


# ---------------------------------------------------------------------------
#  Write Serializers
# ---------------------------------------------------------------------------


class UserToolCreateSerializer(serializers.ModelSerializer):
    """Create serializer for UserTool.

    Only accepts fields the user should set at creation time.
    The `user` field is injected by the view from request.user.
    The tool_name must exist in TOOL_REGISTRY.
    """

    class Meta:
        model = UserTool
        fields = [
            "tool_name",
            "tool_display_name",
            "is_enabled",
            "configuration",
            "description",
            "category",
            "icon",
            "rate_limit",
            "rate_limit_period",
            "requires_approval",
        ]

    def validate_tool_name(self, value):
        """Ensure tool_name exists in the TOOL_REGISTRY."""
        if value not in TOOL_REGISTRY:
            raise serializers.ValidationError(
                f"Unknown tool '{value}'. "
                f"Available: {', '.join(TOOL_REGISTRY.keys())}"
            )
        return value

    def validate_configuration(self, value):
        """Ensure configuration is a dict."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Configuration must be a JSON object.")
        return value

    def validate_rate_limit(self, value):
        """Ensure rate_limit is a positive integer if provided."""
        if value is not None and value < 1:
            raise serializers.ValidationError(
                "Rate limit must be a positive integer."
            )
        return value


class UserToolUpdateSerializer(serializers.ModelSerializer):
    """Update serializer for UserTool — all fields optional.

    Supports partial updates (PATCH). Approval and usage-tracking
    fields are not writable here — use the model's approve() /
    increment_usage() methods.
    """

    class Meta:
        model = UserTool
        fields = [
            "tool_display_name",
            "is_enabled",
            "configuration",
            "description",
            "category",
            "icon",
            "rate_limit",
            "rate_limit_period",
            "requires_approval",
        ]
        extra_kwargs = {field: {"required": False} for field in fields}

    def validate_configuration(self, value):
        """Ensure configuration is a dict."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Configuration must be a JSON object.")
        return value

    def validate_rate_limit(self, value):
        """Ensure rate_limit is a positive integer if provided."""
        if value is not None and value < 1:
            raise serializers.ValidationError(
                "Rate limit must be a positive integer."
            )
        return value
