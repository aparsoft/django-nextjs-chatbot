"""
Serializers for MessageFeedback model.

Follows the operation-based serializer split pattern:
  - MessageFeedbackSerializer        → read (list / retrieve)
  - MessageFeedbackListSerializer    → lightweight read for list actions
  - MessageFeedbackCreateSerializer  → POST create
  - MessageFeedbackUpdateSerializer  → PATCH / PUT update

Business logic lives in the model and service layer — serializers only
handle validation, serialization, and representation.
"""

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from ...models import MessageFeedback


# ---------------------------------------------------------------------------
#  Read Serializers
# ---------------------------------------------------------------------------


class MessageFeedbackSerializer(serializers.ModelSerializer):
    """Read serializer for MessageFeedback (list / retrieve).

    Includes all user-facing fields plus computed properties
    like is_positive, is_negative, sentiment_score.
    """

    is_positive = serializers.BooleanField(read_only=True)
    is_negative = serializers.BooleanField(read_only=True)
    is_neutral = serializers.BooleanField(read_only=True)
    has_issue_report = serializers.BooleanField(read_only=True)
    sentiment_score = serializers.IntegerField(read_only=True)
    user_email = serializers.SerializerMethodField()
    session_title = serializers.SerializerMethodField()

    class Meta:
        model = MessageFeedback
        fields = [
            "id",
            "user",
            "user_email",
            "chat_session",
            "session_title",
            "checkpoint_id",
            "message_index",
            "rating",
            "feedback_categories",
            "feedback_text",
            "reported_issue",
            "message_preview",
            "model_used",
            "is_positive",
            "is_negative",
            "is_neutral",
            "has_issue_report",
            "sentiment_score",
            "reviewed",
            "reviewed_at",
            "reviewed_by",
            "admin_notes",
            "action_taken",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "reviewed",
            "reviewed_at",
            "reviewed_by",
            "admin_notes",
            "action_taken",
            "created_at",
            "updated_at",
        ]

    @extend_schema_field(serializers.EmailField(allow_null=True))
    def get_user_email(self, obj) -> str | None:
        return obj.user.email if obj.user else None

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_session_title(self, obj) -> str | None:
        return obj.chat_session.title if obj.chat_session else None


class MessageFeedbackListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list actions.

    Omits heavy fields (message_preview, admin_notes, feedback_text)
    to keep list responses small and fast.
    """

    is_positive = serializers.BooleanField(read_only=True)
    sentiment_score = serializers.IntegerField(read_only=True)
    user_email = serializers.SerializerMethodField()

    class Meta:
        model = MessageFeedback
        fields = [
            "id",
            "user",
            "user_email",
            "chat_session",
            "checkpoint_id",
            "message_index",
            "rating",
            "reported_issue",
            "model_used",
            "is_positive",
            "sentiment_score",
            "reviewed",
            "action_taken",
            "created_at",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.EmailField(allow_null=True))
    def get_user_email(self, obj) -> str | None:
        return obj.user.email if obj.user else None


# ---------------------------------------------------------------------------
#  Write Serializers
# ---------------------------------------------------------------------------


class MessageFeedbackCreateSerializer(serializers.ModelSerializer):
    """Create serializer for MessageFeedback.

    Only accepts fields the user should set at creation time.
    The `user` field is injected by the view from request.user.
    Admin review fields default and are read-only.
    """

    class Meta:
        model = MessageFeedback
        fields = [
            "chat_session",
            "checkpoint_id",
            "message_index",
            "rating",
            "feedback_categories",
            "feedback_text",
            "reported_issue",
            "message_preview",
            "model_used",
        ]

    def validate_rating(self, value):
        """Ensure rating is a valid choice."""
        valid_ratings = [
            choice[0] for choice in MessageFeedback._meta.get_field("rating").choices
        ]
        if value not in valid_ratings:
            raise serializers.ValidationError(
                f"Invalid rating. Must be one of: {', '.join(valid_ratings)}"
            )
        return value

    def validate_reported_issue(self, value):
        """Ensure reported_issue is a valid choice if provided."""
        if value is None or value == "":
            return value
        valid_issues = [
            choice[0]
            for choice in MessageFeedback._meta.get_field("reported_issue").choices
        ]
        if value not in valid_issues:
            raise serializers.ValidationError(
                f"Invalid issue type. Must be one of: {', '.join(valid_issues)}"
            )
        return value

    def validate_feedback_categories(self, value):
        """Ensure feedback_categories is a list of strings."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Feedback categories must be a list.")
        for item in value:
            if not isinstance(item, str):
                raise serializers.ValidationError(
                    "Each feedback category must be a string."
                )
        return value


class MessageFeedbackUpdateSerializer(serializers.ModelSerializer):
    """Update serializer for MessageFeedback — all fields optional.

    Supports partial updates (PATCH). Admin review fields
    (reviewed, reviewed_at, reviewed_by, action_taken, admin_notes)
    are not writable here — use the model's mark_reviewed() / escalate()
    methods or a dedicated admin endpoint.
    """

    class Meta:
        model = MessageFeedback
        fields = [
            "rating",
            "feedback_categories",
            "feedback_text",
            "reported_issue",
        ]
        extra_kwargs = {field: {"required": False} for field in fields}

    def validate_rating(self, value):
        """Ensure rating is a valid choice."""
        valid_ratings = [
            choice[0] for choice in MessageFeedback._meta.get_field("rating").choices
        ]
        if value not in valid_ratings:
            raise serializers.ValidationError(
                f"Invalid rating. Must be one of: {', '.join(valid_ratings)}"
            )
        return value

    def validate_reported_issue(self, value):
        """Ensure reported_issue is a valid choice if provided."""
        if value is None or value == "":
            return value
        valid_issues = [
            choice[0]
            for choice in MessageFeedback._meta.get_field("reported_issue").choices
        ]
        if value not in valid_issues:
            raise serializers.ValidationError(
                f"Invalid issue type. Must be one of: {', '.join(valid_issues)}"
            )
        return value

    def validate_feedback_categories(self, value):
        """Ensure feedback_categories is a list of strings."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Feedback categories must be a list.")
        for item in value:
            if not isinstance(item, str):
                raise serializers.ValidationError(
                    "Each feedback category must be a string."
                )
        return value
