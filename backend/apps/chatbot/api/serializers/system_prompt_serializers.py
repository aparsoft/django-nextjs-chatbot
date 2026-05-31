"""
Serializers for SystemPromptTemplate model.

Follows the operation-based serializer split pattern:
  - SystemPromptSerializer        → read (list / retrieve)
  - SystemPromptListSerializer    → lightweight read for list actions
  - SystemPromptCreateSerializer  → POST create
  - SystemPromptUpdateSerializer  → PATCH / PUT update

Business logic lives in the model and service layer — serializers only
handle validation, serialization, and representation.
"""

from rest_framework import serializers

from ...models import SystemPromptTemplate


# ---------------------------------------------------------------------------
#  Read Serializers
# ---------------------------------------------------------------------------


class SystemPromptSerializer(serializers.ModelSerializer):
    """Read serializer for SystemPromptTemplate (list / retrieve).

    Includes all user-facing fields plus computed properties
    like average_rating and has_variables.
    """

    average_rating = serializers.FloatField(read_only=True)
    has_variables = serializers.BooleanField(read_only=True)
    category_display = serializers.SerializerMethodField()

    class Meta:
        model = SystemPromptTemplate
        fields = [
            "id",
            "name",
            "slug",
            "content",
            "description",
            "category",
            "category_display",
            "tags",
            "is_default",
            "is_active",
            "is_public",
            "variables",
            "example_variables",
            "recommended_model",
            "recommended_temperature",
            "usage_count",
            "rating_sum",
            "rating_count",
            "average_rating",
            "has_variables",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "slug",
            "usage_count",
            "rating_sum",
            "rating_count",
            "created_at",
            "updated_at",
        ]

    def get_category_display(self, obj) -> str:
        return obj.get_category_display()


class SystemPromptListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list actions.

    Omits the full content and example_variables to keep list
    responses small and fast.
    """

    average_rating = serializers.FloatField(read_only=True)
    has_variables = serializers.BooleanField(read_only=True)
    category_display = serializers.SerializerMethodField()

    class Meta:
        model = SystemPromptTemplate
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "category",
            "category_display",
            "tags",
            "is_default",
            "is_active",
            "is_public",
            "recommended_model",
            "recommended_temperature",
            "usage_count",
            "average_rating",
            "has_variables",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_category_display(self, obj) -> str:
        return obj.get_category_display()


# ---------------------------------------------------------------------------
#  Write Serializers
# ---------------------------------------------------------------------------


class SystemPromptCreateSerializer(serializers.ModelSerializer):
    """Create serializer for SystemPromptTemplate.

    Only accepts fields the user should set at creation time.
    Analytics fields (usage_count, rating_sum, rating_count) default
    to zero and are read-only.
    """

    class Meta:
        model = SystemPromptTemplate
        fields = [
            "name",
            "content",
            "description",
            "category",
            "tags",
            "is_default",
            "is_active",
            "is_public",
            "variables",
            "example_variables",
            "recommended_model",
            "recommended_temperature",
        ]

    def validate_name(self, value):
        """Ensure name is not empty."""
        if not value or not value.strip():
            raise serializers.ValidationError("Name cannot be empty.")
        return value.strip()

    def validate_content(self, value):
        """Ensure content is not empty."""
        if not value or not value.strip():
            raise serializers.ValidationError("Content cannot be empty.")
        return value.strip()

    def validate_tags(self, value):
        """Ensure tags is a list of strings."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Tags must be a list.")
        for item in value:
            if not isinstance(item, str):
                raise serializers.ValidationError("Each tag must be a string.")
        return value

    def validate_variables(self, value):
        """Ensure variables is a list of strings."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Variables must be a list.")
        for item in value:
            if not isinstance(item, str):
                raise serializers.ValidationError(
                    "Each variable name must be a string."
                )
        return value

    def validate_recommended_temperature(self, value):
        """Ensure recommended_temperature is within the valid range (0.0–2.0)."""
        if value is not None and not (0.0 <= value <= 2.0):
            raise serializers.ValidationError(
                "Recommended temperature must be between 0.0 and 2.0."
            )
        return value


class SystemPromptUpdateSerializer(serializers.ModelSerializer):
    """Update serializer for SystemPromptTemplate — all fields optional.

    Supports partial updates (PATCH). Analytics fields (usage_count,
    rating_sum, rating_count) are not writable here — use the model's
    increment_usage() / add_rating() methods.
    """

    class Meta:
        model = SystemPromptTemplate
        fields = [
            "name",
            "content",
            "description",
            "category",
            "tags",
            "is_default",
            "is_active",
            "is_public",
            "variables",
            "example_variables",
            "recommended_model",
            "recommended_temperature",
        ]
        extra_kwargs = {field: {"required": False} for field in fields}

    def validate_name(self, value):
        """Ensure name is not empty."""
        if not value or not value.strip():
            raise serializers.ValidationError("Name cannot be empty.")
        return value.strip()

    def validate_content(self, value):
        """Ensure content is not empty."""
        if not value or not value.strip():
            raise serializers.ValidationError("Content cannot be empty.")
        return value.strip()

    def validate_tags(self, value):
        """Ensure tags is a list of strings."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Tags must be a list.")
        for item in value:
            if not isinstance(item, str):
                raise serializers.ValidationError("Each tag must be a string.")
        return value

    def validate_variables(self, value):
        """Ensure variables is a list of strings."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Variables must be a list.")
        for item in value:
            if not isinstance(item, str):
                raise serializers.ValidationError(
                    "Each variable name must be a string."
                )
        return value

    def validate_recommended_temperature(self, value):
        """Ensure recommended_temperature is within the valid range (0.0–2.0)."""
        if value is not None and not (0.0 <= value <= 2.0):
            raise serializers.ValidationError(
                "Recommended temperature must be between 0.0 and 2.0."
            )
        return value
