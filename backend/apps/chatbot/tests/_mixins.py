"""Shared test helper mixin for chatbot test suite.

Provides reusable factory methods for creating users, sessions,
preferences, documents, and other chatbot models with unique
identifiers to avoid collisions when running with --keepdb.
"""

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from chatbot.models import (
    ChatSession,
    UserPreference,
    TokenUsage,
    MessageFeedback,
    UserDocument,
    SystemPromptTemplate,
    UserTool,
    UserAPIKey,
    TOOL_REGISTRY,
)

User = get_user_model()

_uid_counter = 0


def _next_id():
    """Return a monotonically increasing integer unique across the test run."""
    global _uid_counter
    _uid_counter += 1
    return _uid_counter


class ChatbotTestMixin:
    """Mixin providing factory helpers for chatbot model and API tests."""

    # ------------------------------------------------------------------
    # Users (reuse accounts pattern)
    # ------------------------------------------------------------------

    @staticmethod
    def create_user(role="user", **kwargs):
        """Create a user with unique username/email."""
        n = _next_id()
        defaults = {
            "username": f"chatuser_{n}",
            "email": f"chatuser{n}@test.com",
            "first_name": f"First{n}",
            "last_name": f"Last{n}",
            "role": role,
        }
        defaults.update(kwargs)
        user = User.objects.create_user(
            username=defaults["username"],
            email=defaults["email"],
            password="testpass123!",
            first_name=defaults["first_name"],
            last_name=defaults["last_name"],
        )
        user.role = role
        user.save(update_fields=["role"])
        return user

    @classmethod
    def create_admin_user(cls, **kwargs):
        """Create an admin user."""
        return cls.create_user(role="admin", **kwargs)

    # ------------------------------------------------------------------
    # ChatSession
    # ------------------------------------------------------------------

    @staticmethod
    def create_session(user, **kwargs):
        """Create a chat session for a user."""
        n = _next_id()
        defaults = {
            "title": f"Test Session {n}",
            "model_name": "gpt-4o-mini",
            "temperature": 0.7,
        }
        defaults.update(kwargs)
        return ChatSession.objects.create(user=user, **defaults)

    # ------------------------------------------------------------------
    # UserPreference
    # ------------------------------------------------------------------

    @staticmethod
    def create_preference(user, **kwargs):
        """Create or get user preferences."""
        prefs, _ = UserPreference.objects.get_or_create(user=user, defaults=kwargs)
        return prefs

    # ------------------------------------------------------------------
    # TokenUsage
    # ------------------------------------------------------------------

    @staticmethod
    def create_token_usage(user, session=None, **kwargs):
        """Create a token usage record."""
        from decimal import Decimal

        n = _next_id()
        defaults = {
            "model_name": "gpt-4o-mini",
            "prompt_tokens": 100 + n,
            "completion_tokens": 50 + n,
            "prompt_cost": Decimal("0.000015"),
            "completion_cost": Decimal("0.000030"),
        }
        defaults.update(kwargs)
        usage = TokenUsage.objects.create(
            user=user, chat_session=session, **defaults
        )
        return usage

    # ------------------------------------------------------------------
    # MessageFeedback
    # ------------------------------------------------------------------

    @staticmethod
    def create_feedback(user, session=None, **kwargs):
        """Create a message feedback record."""
        n = _next_id()
        defaults = {
            "rating": "thumbs_up",
            "checkpoint_id": f"checkpoint-{n}",
            "message_index": 0,
            "model_used": "gpt-4o-mini",
        }
        defaults.update(kwargs)
        return MessageFeedback.objects.create(
            user=user, chat_session=session, **defaults
        )

    # ------------------------------------------------------------------
    # UserDocument
    # ------------------------------------------------------------------

    @staticmethod
    def create_document(user, session=None, **kwargs):
        """Create a user document record (no actual file)."""
        n = _next_id()
        defaults = {
            "file_name": f"test_doc_{n}.pdf",
            "file_size": 1024 * n,
            "file_type": "application/pdf",
            "file_extension": ".pdf",
            "processing_status": "pending",
        }
        defaults.update(kwargs)
        return UserDocument.objects.create(
            user=user, chat_session=session, **defaults
        )

    # ------------------------------------------------------------------
    # SystemPromptTemplate
    # ------------------------------------------------------------------

    @staticmethod
    def create_system_prompt(**kwargs):
        """Create a system prompt template."""
        n = _next_id()
        defaults = {
            "name": f"Test Prompt {n}",
            "slug": f"test-prompt-{n}",
            "content": "You are a helpful test assistant.",
            "category": "general",
            "is_active": True,
            "is_public": True,
        }
        defaults.update(kwargs)
        return SystemPromptTemplate.objects.create(**defaults)

    # ------------------------------------------------------------------
    # UserTool
    # ------------------------------------------------------------------

    @staticmethod
    def create_user_tool(user, tool_name=None, **kwargs):
        """Create a user tool record."""
        n = _next_id()
        name = tool_name or "web_search"
        registry = TOOL_REGISTRY.get(name, {})
        defaults = {
            "tool_name": name,
            "tool_display_name": registry.get("display_name", f"Tool {n}"),
            "description": registry.get("description", "Test tool"),
            "category": registry.get("category", "utility"),
            "icon": registry.get("icon", "🔧"),
            "is_enabled": True,
        }
        defaults.update(kwargs)
        return UserTool.objects.create(user=user, **defaults)

    # ------------------------------------------------------------------
    # UserAPIKey
    # ------------------------------------------------------------------

    @staticmethod
    def create_api_key(user, **kwargs):
        """Create a user API key record with a fake encrypted key."""
        from cryptography.fernet import Fernet

        n = _next_id()
        defaults = {
            "provider": "openai",
            "key_name": f"Test Key {n}",
        }
        defaults.update(kwargs)
        key = UserAPIKey.objects.create(user=user, **defaults)
        # Encrypt a fake key
        fernet = Fernet(Fernet.generate_key())
        key.encrypted_key = fernet.encrypt(b"sk-test-fake-key-1234567890")
        key.key_prefix = "sk-test-f"
        key.save()
        return key
