"""Tests for chatbot serializers — validation, fields, operation-based dispatch."""

from django.test import TestCase

from . import ChatbotTestMixin

from chatbot.api.serializers import (
    ChatSessionSerializer,
    ChatSessionListSerializer,
    ChatSessionCreateSerializer,
    ChatSessionUpdateSerializer,
    UserPreferenceSerializer,
    UserPreferenceCreateSerializer,
    UserPreferenceUpdateSerializer,
    TokenUsageSerializer,
    TokenUsageCreateSerializer,
    MessageFeedbackSerializer,
    MessageFeedbackCreateSerializer,
    UserDocumentSerializer,
    UserDocumentCreateSerializer,
    SystemPromptSerializer,
    SystemPromptCreateSerializer,
    SystemPromptUpdateSerializer,
    UserToolSerializer,
    UserToolCreateSerializer,
    UserAPIKeySerializer,
    UserAPIKeyCreateSerializer,
)


# ======================================================================
# ChatSession Serializers
# ======================================================================


class ChatSessionSerializerTests(ChatbotTestMixin, TestCase):
    """Tests for ChatSession read serializers."""

    def test_list_serializer_fields(self):
        """List serializer includes lightweight fields only."""
        user = self.create_user()
        session = self.create_session(user)
        data = ChatSessionListSerializer(session).data
        self.assertIn("id", data)
        self.assertIn("title", data)
        self.assertIn("model_name", data)
        # List serializer omits heavy fields
        self.assertNotIn("metadata", data)
        self.assertNotIn("description", data)

    def test_read_serializer_includes_computed(self):
        """Full read serializer includes computed properties."""
        user = self.create_user()
        session = self.create_session(user)
        data = ChatSessionSerializer(session).data
        self.assertIn("thread_id", data)
        self.assertIn("title_preview", data)
        self.assertIn("is_new", data)


class ChatSessionCreateSerializerTests(ChatbotTestMixin, TestCase):
    """Tests for ChatSessionCreateSerializer."""

    def test_valid_create_data(self):
        """Valid data passes validation."""
        data = {
            "title": "Test Chat",
            "model_name": "gpt-4o-mini",
            "temperature": 0.7,
        }
        serializer = ChatSessionCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_temperature_range_validation(self):
        """Temperature outside 0.0–2.0 is rejected."""
        data = {"title": "Test", "temperature": 3.0}
        serializer = ChatSessionCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("temperature", serializer.errors)

    def test_temperature_zero_valid(self):
        """Temperature 0.0 is valid."""
        data = {"title": "Test", "temperature": 0.0}
        serializer = ChatSessionCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_summarization_threshold_positive(self):
        """Summarization threshold must be positive."""
        data = {"title": "Test", "summarization_threshold": 0}
        serializer = ChatSessionCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("summarization_threshold", serializer.errors)


class ChatSessionUpdateSerializerTests(ChatbotTestMixin, TestCase):
    """Tests for ChatSessionUpdateSerializer."""

    def test_all_fields_optional(self):
        """Partial update accepts single field."""
        serializer = ChatSessionUpdateSerializer(data={"title": "Updated"}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_temperature_validation_on_update(self):
        """Temperature validation also applies to updates."""
        serializer = ChatSessionUpdateSerializer(
            data={"temperature": -1.0}, partial=True
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("temperature", serializer.errors)


# ======================================================================
# UserPreference Serializers
# ======================================================================


class UserPreferenceSerializerTests(ChatbotTestMixin, TestCase):
    """Tests for UserPreference serializers."""

    def test_read_serializer_includes_computed(self):
        """Read serializer includes computed properties."""
        user = self.create_user()
        prefs = self.create_preference(user)
        data = UserPreferenceSerializer(prefs).data
        self.assertIn("has_usage_limits", data)
        self.assertIn("is_dark_mode", data)
        self.assertIn("user_email", data)

    def test_create_serializer_temperature_validation(self):
        """Temperature outside 0.0–2.0 is rejected."""
        data = {"default_temperature": 5.0}
        serializer = UserPreferenceCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("default_temperature", serializer.errors)

    def test_create_serializer_max_tokens_positive(self):
        """Max tokens must be positive."""
        data = {"default_max_tokens": 0}
        serializer = UserPreferenceCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("default_max_tokens", serializer.errors)

    def test_update_serializer_all_optional(self):
        """Update serializer accepts partial data."""
        data = {"theme": "dark"}
        serializer = UserPreferenceUpdateSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_update_serializer_temperature_validation(self):
        """Temperature validation applies on update too."""
        data = {"default_temperature": -0.5}
        serializer = UserPreferenceUpdateSerializer(data=data)
        self.assertFalse(serializer.is_valid())


# ======================================================================
# TokenUsage Serializers
# ======================================================================


class TokenUsageSerializerTests(ChatbotTestMixin, TestCase):
    """Tests for TokenUsage serializers."""

    def test_create_serializer_negative_tokens_rejected(self):
        """Negative token counts are rejected."""
        data = {
            "model_name": "gpt-4o-mini",
            "prompt_tokens": -10,
            "completion_tokens": 50,
        }
        serializer = TokenUsageCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("prompt_tokens", serializer.errors)

    def test_create_serializer_valid_data(self):
        """Valid data passes."""
        data = {
            "model_name": "gpt-4o-mini",
            "prompt_tokens": 100,
            "completion_tokens": 50,
        }
        serializer = TokenUsageCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_read_serializer_fields(self):
        """Read serializer includes cost and token fields."""
        user = self.create_user()
        session = self.create_session(user)
        usage = self.create_token_usage(user, session)
        data = TokenUsageSerializer(usage).data
        self.assertIn("total_tokens", data)
        self.assertIn("total_cost", data)
        self.assertIn("user_email", data)


# ======================================================================
# MessageFeedback Serializers
# ======================================================================


class MessageFeedbackSerializerTests(ChatbotTestMixin, TestCase):
    """Tests for MessageFeedback serializers."""

    def test_create_serializer_valid_rating(self):
        """Valid rating passes."""
        data = {"rating": "thumbs_up"}
        serializer = MessageFeedbackCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_create_serializer_invalid_rating(self):
        """Invalid rating is rejected."""
        data = {"rating": "super_bad"}
        serializer = MessageFeedbackCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("rating", serializer.errors)

    def test_create_serializer_feedback_categories_list(self):
        """Feedback categories must be a list."""
        data = {"rating": "thumbs_up", "feedback_categories": "not_a_list"}
        serializer = MessageFeedbackCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("feedback_categories", serializer.errors)


# ======================================================================
# UserDocument Serializers
# ======================================================================


class UserDocumentSerializerTests(ChatbotTestMixin, TestCase):
    """Tests for UserDocument serializers."""

    def test_read_serializer_computed_fields(self):
        """Read serializer includes computed properties."""
        user = self.create_user()
        doc = self.create_document(user)
        data = UserDocumentSerializer(doc).data
        self.assertIn("file_size_mb", data)
        self.assertIn("file_size_display", data)
        self.assertIn("has_embeddings", data)
        self.assertIn("is_pending", data)


# ======================================================================
# SystemPrompt Serializers
# ======================================================================


class SystemPromptSerializerTests(ChatbotTestMixin, TestCase):
    """Tests for SystemPrompt serializers."""

    def test_create_serializer_empty_name_rejected(self):
        """Empty name is rejected."""
        data = {"name": "", "content": "test", "slug": "test"}
        serializer = SystemPromptCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)

    def test_create_serializer_empty_content_rejected(self):
        """Empty content is rejected."""
        data = {"name": "Test", "content": "", "slug": "test"}
        serializer = SystemPromptCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("content", serializer.errors)

    def test_create_serializer_valid_data(self):
        """Valid data passes."""
        data = {
            "name": "Test Prompt",
            "slug": "test-prompt",
            "content": "You are helpful.",
            "category": "general",
        }
        serializer = SystemPromptCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_create_serializer_tags_must_be_list(self):
        """Tags must be a list."""
        data = {
            "name": "Test",
            "content": "test",
            "slug": "test",
            "tags": "not_a_list",
        }
        serializer = SystemPromptCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("tags", serializer.errors)

    def test_update_serializer_all_optional(self):
        """Update serializer accepts partial data."""
        data = {"name": "Updated"}
        serializer = SystemPromptUpdateSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_temperature_range_validation(self):
        """Recommended temperature must be 0.0–2.0."""
        data = {"name": "Test", "content": "x", "recommended_temperature": 5.0}
        serializer = SystemPromptCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("recommended_temperature", serializer.errors)


# ======================================================================
# UserTool Serializers
# ======================================================================


class UserToolSerializerTests(ChatbotTestMixin, TestCase):
    """Tests for UserTool serializers."""

    def test_create_serializer_unknown_tool_rejected(self):
        """Tool name not in TOOL_REGISTRY is rejected."""
        data = {"tool_name": "nonexistent_tool"}
        serializer = UserToolCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("tool_name", serializer.errors)

    def test_create_serializer_valid_tool(self):
        """Valid tool name passes."""
        data = {"tool_name": "web_search"}
        serializer = UserToolCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_create_serializer_config_must_be_dict(self):
        """Configuration must be a JSON object."""
        data = {"tool_name": "web_search", "configuration": "not_a_dict"}
        serializer = UserToolCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("configuration", serializer.errors)


# ======================================================================
# UserAPIKey Serializers
# ======================================================================


class UserAPIKeySerializerTests(ChatbotTestMixin, TestCase):
    """Tests for UserAPIKey serializers."""

    def test_create_serializer_empty_key_rejected(self):
        """Empty API key is rejected."""
        data = {"provider": "openai", "key_name": "Test", "api_key": ""}
        serializer = UserAPIKeyCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("api_key", serializer.errors)

    def test_create_serializer_short_key_rejected(self):
        """Short API key is rejected."""
        data = {"provider": "openai", "key_name": "Test", "api_key": "abc"}
        serializer = UserAPIKeyCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("api_key", serializer.errors)

    def test_create_serializer_valid_data(self):
        """Valid data passes."""
        data = {
            "provider": "openai",
            "key_name": "My Key",
            "api_key": "sk-proj-abcdef1234567890",
        }
        serializer = UserAPIKeyCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_create_serializer_daily_limit_positive(self):
        """Daily limit must be positive if provided."""
        data = {
            "provider": "openai",
            "key_name": "Test",
            "api_key": "sk-proj-abcdef1234567890",
            "daily_limit": 0,
        }
        serializer = UserAPIKeyCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("daily_limit", serializer.errors)

    def test_read_serializer_no_raw_key(self):
        """Read serializer never includes the raw key."""
        user = self.create_user()
        key = self.create_api_key(user)
        data = UserAPIKeySerializer(key).data
        self.assertNotIn("encrypted_key", data)
        self.assertNotIn("api_key", data)
        self.assertIn("display_key", data)
