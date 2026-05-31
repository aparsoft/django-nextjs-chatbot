"""
Serializers for TokenUsage model.

Follows the operation-based serializer split pattern:
  - TokenUsageSerializer        → read (list / retrieve)
  - TokenUsageListSerializer    → lightweight read for list actions
  - TokenUsageCreateSerializer  → POST create

TokenUsage records are generally created programmatically via
TokenUsage.create_from_response(), but a create serializer is
provided for manual / testing use.

There is no update serializer — usage records are immutable once
created.
"""

from rest_framework import serializers

from ...models import TokenUsage


# ---------------------------------------------------------------------------
#  Read Serializers
# ---------------------------------------------------------------------------


class TokenUsageSerializer(serializers.ModelSerializer):
    """Read serializer for TokenUsage (list / retrieve).

    Includes all user-facing fields. Cost fields are output as
    floats (via DRF's decimal handling) for JSON compatibility.
    """

    user_email = serializers.SerializerMethodField()

    class Meta:
        model = TokenUsage
        fields = [
            "id",
            "user",
            "user_email",
            "chat_session",
            "model_name",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "reasoning_tokens",
            "prompt_cost",
            "completion_cost",
            "total_cost",
            "request_type",
            "endpoint",
            "response_time_ms",
            "was_cached",
            "had_error",
            "error_message",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "chat_session",
            "model_name",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "reasoning_tokens",
            "prompt_cost",
            "completion_cost",
            "total_cost",
            "created_at",
            "updated_at",
        ]

    def get_user_email(self, obj) -> str | None:
        return obj.user.email if obj.user else None


class TokenUsageListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list actions.

    Omits verbose fields (error_message, metadata, endpoint) to
    keep list responses small and fast.
    """

    user_email = serializers.SerializerMethodField()

    class Meta:
        model = TokenUsage
        fields = [
            "id",
            "user",
            "user_email",
            "chat_session",
            "model_name",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "total_cost",
            "request_type",
            "response_time_ms",
            "was_cached",
            "had_error",
            "created_at",
        ]
        read_only_fields = fields

    def get_user_email(self, obj) -> str | None:
        return obj.user.email if obj.user else None


# ---------------------------------------------------------------------------
#  Write Serializers
# ---------------------------------------------------------------------------


class TokenUsageCreateSerializer(serializers.ModelSerializer):
    """Create serializer for TokenUsage.

    Only accepts fields that should be set at creation time.
    Token counts and costs are calculated automatically in the
    model's save() method.
    """

    class Meta:
        model = TokenUsage
        fields = [
            "chat_session",
            "model_name",
            "prompt_tokens",
            "completion_tokens",
            "reasoning_tokens",
            "request_type",
            "endpoint",
            "response_time_ms",
            "was_cached",
            "had_error",
            "error_message",
            "metadata",
        ]

    def validate_prompt_tokens(self, value):
        """Ensure prompt_tokens is non-negative."""
        if value < 0:
            raise serializers.ValidationError(
                "Prompt tokens must be non-negative."
            )
        return value

    def validate_completion_tokens(self, value):
        """Ensure completion_tokens is non-negative."""
        if value < 0:
            raise serializers.ValidationError(
                "Completion tokens must be non-negative."
            )
        return value

    def validate_reasoning_tokens(self, value):
        """Ensure reasoning_tokens is non-negative if provided."""
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "Reasoning tokens must be non-negative."
            )
        return value
