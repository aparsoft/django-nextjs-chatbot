"""
Serializers for ChatSession model.

Follows the operation-based serializer split pattern:
  - ChatSessionSerializer        → read (list / retrieve)
  - ChatSessionListSerializer    → lightweight read for list actions
  - ChatSessionCreateSerializer  → POST create
  - ChatSessionUpdateSerializer  → PATCH / PUT update

Business logic lives in ChatSessionService — serializers only handle
validation, serialization, and representation.
"""

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from ...models import ChatSession


# ---------------------------------------------------------------------------
#  Read Serializers
# ---------------------------------------------------------------------------


class ChatSessionSerializer(serializers.ModelSerializer):
    """Read serializer for ChatSession (list / retrieve).

    Includes all user-facing fields plus computed properties
    like thread_id and title_preview.
    """

    thread_id = serializers.CharField(read_only=True)
    title_preview = serializers.CharField(read_only=True)
    is_new = serializers.BooleanField(read_only=True)
    user_email = serializers.SerializerMethodField()

    class Meta:
        model = ChatSession
        fields = [
            "id",
            "user",
            "user_email",
            "title",
            "title_preview",
            "description",
            "model_name",
            "temperature",
            "enable_summarization",
            "summarization_threshold",
            "is_active",
            "is_archived",
            "is_pinned",
            "is_new",
            "thread_id",
            "tags",
            "metadata",
            "message_count",
            "total_tokens_used",
            "last_message_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "message_count",
            "total_tokens_used",
            "last_message_at",
            "created_at",
            "updated_at",
        ]

    @extend_schema_field(serializers.EmailField(allow_null=True))
    def get_user_email(self, obj) -> str | None:
        return obj.user.email if obj.user else None


class ChatSessionListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list actions.

    Omits heavy fields (metadata, description) to keep list
    responses small and fast.
    """

    thread_id = serializers.CharField(read_only=True)
    title_preview = serializers.CharField(read_only=True)
    is_new = serializers.BooleanField(read_only=True)

    class Meta:
        model = ChatSession
        fields = [
            "id",
            "title",
            "title_preview",
            "model_name",
            "is_active",
            "is_archived",
            "is_pinned",
            "is_new",
            "thread_id",
            "message_count",
            "last_message_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
#  Write Serializers
# ---------------------------------------------------------------------------


class ChatSessionCreateSerializer(serializers.ModelSerializer):
    """Create serializer for ChatSession.

    Only accepts fields the user should set at creation time.
    The `user` field is injected by the view from request.user.
    Session analytics fields default to zero and are read-only.
    Includes `id` and timestamps so the client can navigate to the
    newly created session immediately after POST.
    """

    id = serializers.UUIDField(read_only=True)
    thread_id = serializers.CharField(read_only=True)
    title_preview = serializers.CharField(read_only=True)
    is_new = serializers.BooleanField(read_only=True)
    user_email = serializers.SerializerMethodField()

    class Meta:
        model = ChatSession
        fields = [
            "id",
            "user",
            "user_email",
            "title",
            "title_preview",
            "description",
            "model_name",
            "temperature",
            "enable_summarization",
            "summarization_threshold",
            "is_active",
            "is_archived",
            "is_pinned",
            "is_new",
            "thread_id",
            "tags",
            "metadata",
            "message_count",
            "total_tokens_used",
            "last_message_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "message_count",
            "total_tokens_used",
            "last_message_at",
            "created_at",
            "updated_at",
        ]

    @extend_schema_field(serializers.EmailField(allow_null=True))
    def get_user_email(self, obj) -> str | None:
        return obj.user.email if obj.user else None

    def validate_temperature(self, value):
        """Ensure temperature is within the valid range (0.0–2.0)."""
        if not (0.0 <= value <= 2.0):
            raise serializers.ValidationError(
                "Temperature must be between 0.0 and 2.0."
            )
        return value

    def validate_summarization_threshold(self, value):
        """Ensure summarization threshold is a positive integer."""
        if value < 1:
            raise serializers.ValidationError(
                "Summarization threshold must be at least 1."
            )
        return value


class ChatSessionUpdateSerializer(serializers.ModelSerializer):
    """Update serializer for ChatSession — all fields optional.

    Supports partial updates (PATCH). Analytics fields (message_count,
    total_tokens_used, last_message_at) are never writable through
    this serializer — use ChatSessionService.update_session_analytics().
    """

    class Meta:
        model = ChatSession
        fields = [
            "title",
            "description",
            "model_name",
            "temperature",
            "enable_summarization",
            "summarization_threshold",
            "is_active",
            "is_archived",
            "is_pinned",
            "tags",
            "metadata",
        ]
        extra_kwargs = {field: {"required": False} for field in fields}

    def validate_temperature(self, value):
        """Ensure temperature is within the valid range (0.0–2.0)."""
        if not (0.0 <= value <= 2.0):
            raise serializers.ValidationError(
                "Temperature must be between 0.0 and 2.0."
            )
        return value

    def validate_summarization_threshold(self, value):
        """Ensure summarization threshold is a positive integer."""
        if value < 1:
            raise serializers.ValidationError(
                "Summarization threshold must be at least 1."
            )
        return value
