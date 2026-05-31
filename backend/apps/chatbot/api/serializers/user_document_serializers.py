"""
Serializers for UserDocument model.

Follows the operation-based serializer split pattern:
  - UserDocumentSerializer        → read (list / retrieve)
  - UserDocumentListSerializer    → lightweight read for list actions
  - UserDocumentCreateSerializer  → POST create
  - UserDocumentUpdateSerializer  → PATCH / PUT update

The uploaded file is handled via a file field in the create serializer.
Processing-status transitions are handled by the model's state-machine
methods — not through serializers.
"""

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from ...models import UserDocument


# ---------------------------------------------------------------------------
#  Read Serializers
# ---------------------------------------------------------------------------


class UserDocumentSerializer(serializers.ModelSerializer):
    """Read serializer for UserDocument (list / retrieve).

    Includes all user-facing fields plus computed properties
    like file_size_mb, file_size_display, and has_embeddings.
    """

    file_size_mb = serializers.FloatField(read_only=True)
    file_size_display = serializers.CharField(read_only=True)
    is_processable = serializers.BooleanField(read_only=True)
    has_embeddings = serializers.BooleanField(read_only=True)
    is_pending = serializers.BooleanField(read_only=True)
    is_processing = serializers.BooleanField(read_only=True)
    is_completed = serializers.BooleanField(read_only=True)
    is_failed = serializers.BooleanField(read_only=True)
    user_email = serializers.SerializerMethodField()

    class Meta:
        model = UserDocument
        fields = [
            "id",
            "user",
            "user_email",
            "chat_session",
            "file",
            "file_name",
            "file_size",
            "file_size_mb",
            "file_size_display",
            "file_type",
            "file_extension",
            "processing_status",
            "processed_at",
            "vector_collection_name",
            "chunk_count",
            "title",
            "description",
            "tags",
            "extracted_metadata",
            "page_count",
            "word_count",
            "is_active",
            "is_shared",
            "share_settings",
            "is_processable",
            "has_embeddings",
            "is_pending",
            "is_processing",
            "is_completed",
            "is_failed",
            "processing_error",
            "retry_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "file_name",
            "file_size",
            "file_extension",
            "processing_status",
            "processed_at",
            "vector_collection_name",
            "vector_store_ids",
            "chunk_count",
            "processing_error",
            "retry_count",
            "created_at",
            "updated_at",
        ]

    @extend_schema_field(serializers.EmailField(allow_null=True))
    def get_user_email(self, obj) -> str | None:
        return obj.user.email if obj.user else None


class UserDocumentListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list actions.

    Omits heavy fields (extracted_metadata, share_settings,
    vector references) to keep list responses small and fast.
    """

    file_size_display = serializers.CharField(read_only=True)
    is_completed = serializers.BooleanField(read_only=True)
    user_email = serializers.SerializerMethodField()

    class Meta:
        model = UserDocument
        fields = [
            "id",
            "user",
            "user_email",
            "file_name",
            "file_size",
            "file_size_display",
            "file_type",
            "processing_status",
            "chunk_count",
            "title",
            "is_active",
            "is_completed",
            "page_count",
            "tags",
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


class UserDocumentCreateSerializer(serializers.ModelSerializer):
    """Create serializer for UserDocument.

    Accepts the file upload along with optional metadata. The `user`
    field is injected by the view from request.user. File metadata
    (name, size, extension) is extracted automatically in the model's
    save() method.
    """

    file = serializers.FileField(
        help_text="Document file to upload (PDF, DOCX, TXT, MD, CSV)",
    )

    class Meta:
        model = UserDocument
        fields = [
            "chat_session",
            "file",
            "title",
            "description",
            "tags",
        ]

    def validate_file(self, value):
        """Validate the uploaded file."""
        max_size_mb = 50
        max_size_bytes = max_size_mb * 1024 * 1024

        if value.size > max_size_bytes:
            raise serializers.ValidationError(
                f"File size exceeds the {max_size_mb}MB limit."
            )

        allowed_extensions = [
            ".pdf",
            ".docx",
            ".doc",
            ".txt",
            ".md",
            ".csv",
        ]

        import os

        ext = os.path.splitext(value.name)[1].lower()
        if ext not in allowed_extensions:
            raise serializers.ValidationError(
                f"Unsupported file type '{ext}'. "
                f"Allowed: {', '.join(allowed_extensions)}"
            )

        return value

    def validate_tags(self, value):
        """Ensure tags is a list of strings."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Tags must be a list.")
        for item in value:
            if not isinstance(item, str):
                raise serializers.ValidationError("Each tag must be a string.")
        return value


class UserDocumentUpdateSerializer(serializers.ModelSerializer):
    """Update serializer for UserDocument — all fields optional.

    Supports partial updates (PATCH). Processing status and vector
    store fields are not writable here — use the model's
    mark_processing_*() methods.
    """

    class Meta:
        model = UserDocument
        fields = [
            "title",
            "description",
            "tags",
            "is_active",
            "is_shared",
            "share_settings",
        ]
        extra_kwargs = {field: {"required": False} for field in fields}

    def validate_tags(self, value):
        """Ensure tags is a list of strings."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Tags must be a list.")
        for item in value:
            if not isinstance(item, str):
                raise serializers.ValidationError("Each tag must be a string.")
        return value
