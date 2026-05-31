"""Tests for chatbot API ViewSets — CRUD, custom actions, permissions.

Tests the action-based ViewSet endpoints auto-discovered by DefaultRouter:
  /api/v1/chatbot/chat-sessions/          — CRUD + archive, activate, pin, analytics
  /api/v1/chatbot/preferences/            — CRUD + me, session-config, reset-defaults
  /api/v1/chatbot/token-usage/            — Read-only + usage-stats, daily-usage, check-limits
  /api/v1/chatbot/message-feedback/       — CRUD + review, stats
  /api/v1/chatbot/documents/              — CRUD + process, retry, status, storage-stats
  /api/v1/chatbot/system-prompts/         — CRUD + rate, duplicate, render, search, default
  /api/v1/chatbot/tools/                  — CRUD + activate, deactivate, registry, seed, enabled
  /api/v1/chatbot/api-keys/               — CRUD + validate, set-default, deactivate, providers
"""

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from . import ChatbotTestMixin

BASE = "/api/v1/chatbot/"


# ======================================================================
# ChatSession ViewSet
# ======================================================================


class ChatSessionViewSetCRUDTests(ChatbotTestMixin, TestCase):
    """Tests for basic CRUD on ChatSessionViewSet."""

    def setUp(self):
        self.client = APIClient()
        self.user = self.create_user()
        self.admin = self.create_admin_user()
        self.session = self.create_session(self.user)

    def test_list_own_sessions(self):
        """User sees only their own sessions."""
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{BASE}chat-sessions/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["results"]), 1)

    def test_list_sessions_admin_sees_all(self):
        """Admin sees all sessions."""
        self.client.force_authenticate(self.admin)
        resp = self.client.get(f"{BASE}chat-sessions/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["results"]), 1)

    def test_retrieve_own_session(self):
        """User can retrieve their own session."""
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{BASE}chat-sessions/{self.session.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["title"], self.session.title)

    def test_create_session(self):
        """User can create a new session."""
        self.create_preference(self.user)
        self.client.force_authenticate(self.user)
        resp = self.client.post(f"{BASE}chat-sessions/", {"title": "New Chat"})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["title"], "New Chat")

    def test_update_session(self):
        """User can partial-update their session."""
        self.client.force_authenticate(self.user)
        resp = self.client.patch(
            f"{BASE}chat-sessions/{self.session.id}/",
            {"title": "Updated Title"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["title"], "Updated Title")

    def test_delete_session_soft_deletes(self):
        """DELETE soft-deletes the session."""
        self.client.force_authenticate(self.user)
        resp = self.client.delete(f"{BASE}chat-sessions/{self.session.id}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.session.refresh_from_db()
        self.assertFalse(self.session.is_active)
        self.assertTrue(self.session.is_archived)

    def test_unauthenticated_rejected(self):
        """Unauthenticated requests are rejected."""
        resp = self.client.get(f"{BASE}chat-sessions/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class ChatSessionViewSetActionTests(ChatbotTestMixin, TestCase):
    """Tests for custom @action routes on ChatSessionViewSet."""

    def setUp(self):
        self.client = APIClient()
        self.user = self.create_user()
        self.session = self.create_session(self.user)

    def test_archive_action(self):
        """POST archive/ archives the session."""
        self.client.force_authenticate(self.user)
        resp = self.client.post(f"{BASE}chat-sessions/{self.session.id}/archive/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.session.refresh_from_db()
        self.assertTrue(self.session.is_archived)

    def test_activate_action(self):
        """POST activate/ reactivates an archived session."""
        self.session.archive()
        self.client.force_authenticate(self.user)
        resp = self.client.post(f"{BASE}chat-sessions/{self.session.id}/activate/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.session.refresh_from_db()
        self.assertTrue(self.session.is_active)

    def test_pin_action(self):
        """POST pin/ toggles pin status."""
        self.client.force_authenticate(self.user)
        resp = self.client.post(f"{BASE}chat-sessions/{self.session.id}/pin/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.session.refresh_from_db()
        self.assertTrue(self.session.is_pinned)

    def test_archived_list(self):
        """GET archived/ returns archived sessions."""
        self.session.archive()
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{BASE}chat-sessions/archived/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_pinned_list(self):
        """GET pinned/ returns pinned sessions."""
        self.session.toggle_pin()
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{BASE}chat-sessions/pinned/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_stats_action(self):
        """GET stats/ returns aggregate statistics."""
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{BASE}chat-sessions/stats/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("total_sessions", resp.data)

    def test_analytics_action(self):
        """GET {id}/analytics/ returns session analytics."""
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{BASE}chat-sessions/{self.session.id}/analytics/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


# ======================================================================
# UserPreference ViewSet
# ======================================================================


class UserPreferenceViewSetTests(ChatbotTestMixin, TestCase):
    """Tests for UserPreferenceViewSet."""

    def setUp(self):
        self.client = APIClient()
        self.user = self.create_user()
        self.prefs = self.create_preference(self.user)

    def test_me_returns_preferences(self):
        """GET me/ returns user's preferences."""
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{BASE}preferences/me/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["default_model"], self.prefs.default_model)

    def test_me_creates_if_missing(self):
        """GET me/ auto-creates preferences if missing."""
        new_user = self.create_user()
        self.client.force_authenticate(new_user)
        resp = self.client.get(f"{BASE}preferences/me/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_session_config(self):
        """GET session-config/ returns config dict."""
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{BASE}preferences/session-config/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("model_name", resp.data)

    def test_reset_defaults(self):
        """POST reset-defaults/ restores defaults."""
        self.prefs.default_model = "gpt-4o"
        self.prefs.save()
        self.client.force_authenticate(self.user)
        resp = self.client.post(f"{BASE}preferences/reset-defaults/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.prefs.refresh_from_db()
        self.assertEqual(self.prefs.default_model, "gpt-5-mini")

    def test_update_preferences(self):
        """PATCH updates preference fields."""
        self.client.force_authenticate(self.user)
        resp = self.client.patch(
            f"{BASE}preferences/{self.prefs.id}/",
            {"theme": "dark"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.prefs.refresh_from_db()
        self.assertEqual(self.prefs.theme, "dark")


# ======================================================================
# TokenUsage ViewSet (read-only)
# ======================================================================


class TokenUsageViewSetTests(ChatbotTestMixin, TestCase):
    """Tests for TokenUsageViewSet (read-only)."""

    def setUp(self):
        self.client = APIClient()
        self.user = self.create_user()
        self.session = self.create_session(self.user)
        self.usage = self.create_token_usage(self.user, self.session)

    def test_list_usage(self):
        """GET list returns user's usage records."""
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{BASE}token-usage/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["results"]), 1)

    def test_create_not_allowed(self):
        """POST is not allowed (read-only)."""
        self.client.force_authenticate(self.user)
        resp = self.client.post(f"{BASE}token-usage/", {"model_name": "test"})
        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_usage_stats(self):
        """GET usage-stats/ returns aggregated stats."""
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{BASE}token-usage/usage-stats/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("total_requests", resp.data)

    def test_daily_usage(self):
        """GET daily-usage/ returns today's usage."""
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{BASE}token-usage/daily-usage/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_check_limits(self):
        """GET check-limits/ returns limit status."""
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{BASE}token-usage/check-limits/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


# ======================================================================
# MessageFeedback ViewSet
# ======================================================================


class MessageFeedbackViewSetTests(ChatbotTestMixin, TestCase):
    """Tests for MessageFeedbackViewSet."""

    def setUp(self):
        self.client = APIClient()
        self.user = self.create_user()
        self.admin = self.create_admin_user()
        self.session = self.create_session(self.user)

    def test_create_feedback(self):
        """POST creates feedback for a session."""
        self.client.force_authenticate(self.user)
        resp = self.client.post(f"{BASE}message-feedback/", {
            "rating": "thumbs_up",
            "checkpoint_id": "cp-123",
            "message_index": 0,
            "model_used": "gpt-4o-mini",
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_list_own_feedback(self):
        """User sees only their own feedback."""
        self.create_feedback(self.user, self.session)
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{BASE}message-feedback/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["results"]), 1)

    def test_review_action_admin(self):
        """POST review/ allows admin to review feedback."""
        fb = self.create_feedback(self.user, self.session)
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            f"{BASE}message-feedback/{fb.id}/review/",
            {"admin_notes": "Reviewed", "action_taken": "none"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        fb.refresh_from_db()
        self.assertTrue(fb.reviewed)

    def test_stats_action(self):
        """GET stats/ returns feedback statistics."""
        self.create_feedback(self.user, self.session, rating="thumbs_up")
        self.create_feedback(self.user, self.session, rating="thumbs_down")
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{BASE}message-feedback/stats/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["total_feedback"], 2)


# ======================================================================
# UserDocument ViewSet
# ======================================================================


class UserDocumentViewSetTests(ChatbotTestMixin, TestCase):
    """Tests for UserDocumentViewSet."""

    def setUp(self):
        self.client = APIClient()
        self.user = self.create_user()
        self.session = self.create_session(self.user)
        self.doc = self.create_document(self.user, self.session)

    def test_list_documents(self):
        """GET list returns user's documents."""
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{BASE}documents/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["results"]), 1)

    def test_retrieve_document(self):
        """GET retrieve returns document details."""
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{BASE}documents/{self.doc.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("file_size_display", resp.data)

    def test_process_action(self):
        """POST process/ starts document processing."""
        self.client.force_authenticate(self.user)
        resp = self.client.post(f"{BASE}documents/{self.doc.id}/process/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("processing", resp.data["status"])

    def test_process_already_completed(self):
        """POST process/ on completed doc returns 409."""
        self.doc.processing_status = "completed"
        self.doc.save()
        self.client.force_authenticate(self.user)
        resp = self.client.post(f"{BASE}documents/{self.doc.id}/process/")
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    def test_retry_action(self):
        """POST retry/ retries failed processing."""
        self.doc.mark_processing_failed("test error")
        self.client.force_authenticate(self.user)
        resp = self.client.post(f"{BASE}documents/{self.doc.id}/retry/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_status_action(self):
        """GET status/ returns processing status."""
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{BASE}documents/{self.doc.id}/status/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("status", resp.data)

    def test_storage_stats(self):
        """GET storage-stats/ returns storage usage."""
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{BASE}documents/storage-stats/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("total_documents", resp.data)

    def test_processing_stats(self):
        """GET processing-stats/ returns processing statistics."""
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{BASE}documents/processing-stats/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("pending", resp.data)


# ======================================================================
# SystemPrompt ViewSet
# ======================================================================


class SystemPromptViewSetTests(ChatbotTestMixin, TestCase):
    """Tests for SystemPromptViewSet."""

    def setUp(self):
        self.client = APIClient()
        self.user = self.create_user()
        self.admin = self.create_admin_user()
        self.prompt = self.create_system_prompt()

    def test_list_public_prompts(self):
        """Regular user sees active public prompts."""
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{BASE}system-prompts/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_create_prompt_admin_only(self):
        """Admin can create a new prompt."""
        self.client.force_authenticate(self.admin)
        resp = self.client.post(f"{BASE}system-prompts/", {
            "name": "New Prompt",
            "slug": "new-prompt",
            "content": "You are a test assistant.",
            "category": "general",
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_create_prompt_regular_user_forbidden(self):
        """Regular user cannot create prompts."""
        self.client.force_authenticate(self.user)
        resp = self.client.post(f"{BASE}system-prompts/", {
            "name": "Bad", "slug": "bad", "content": "bad",
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_rate_action(self):
        """POST rate/ adds a rating."""
        self.client.force_authenticate(self.user)
        resp = self.client.post(
            f"{BASE}system-prompts/{self.prompt.id}/rate/",
            {"rating": 4},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("average_rating", resp.data)

    def test_duplicate_action(self):
        """POST duplicate/ creates a copy."""
        self.client.force_authenticate(self.admin)
        resp = self.client.post(f"{BASE}system-prompts/{self.prompt.id}/duplicate/")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertNotEqual(resp.data["id"], str(self.prompt.id))

    def test_render_action(self):
        """POST render/ returns rendered prompt."""
        prompt = self.create_system_prompt(content="Hello {name}!")
        self.client.force_authenticate(self.user)
        resp = self.client.post(
            f"{BASE}system-prompts/{prompt.id}/render/",
            {"variables": {"name": "World"}},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["rendered_prompt"], "Hello World!")

    def test_search_action(self):
        """GET search/?q= returns matching prompts."""
        self.create_system_prompt(name="Python Expert")
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{BASE}system-prompts/search/?q=Python")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_search_missing_query(self):
        """GET search/ without q param returns 400."""
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{BASE}system-prompts/search/")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_default_action(self):
        """GET default/ returns the default template."""
        self.create_system_prompt(is_default=True)
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{BASE}system-prompts/default/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["is_default"])


# ======================================================================
# UserTool ViewSet
# ======================================================================


class UserToolViewSetTests(ChatbotTestMixin, TestCase):
    """Tests for UserToolViewSet."""

    def setUp(self):
        self.client = APIClient()
        self.user = self.create_user()
        self.tool = self.create_user_tool(self.user, tool_name="web_search")

    def test_list_tools(self):
        """GET list returns user's tools."""
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{BASE}tools/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_create_tool_from_registry(self):
        """POST creates a tool from TOOL_REGISTRY."""
        self.client.force_authenticate(self.user)
        resp = self.client.post(f"{BASE}tools/", {"tool_name": "calculator"})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_activate_action(self):
        """POST activate/ enables a tool."""
        self.tool.deactivate()
        self.client.force_authenticate(self.user)
        resp = self.client.post(f"{BASE}tools/{self.tool.id}/activate/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.tool.refresh_from_db()
        self.assertTrue(self.tool.is_enabled)

    def test_deactivate_action(self):
        """POST deactivate/ disables a tool."""
        self.client.force_authenticate(self.user)
        resp = self.client.post(f"{BASE}tools/{self.tool.id}/deactivate/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.tool.refresh_from_db()
        self.assertFalse(self.tool.is_enabled)

    def test_registry_action(self):
        """GET registry/ returns all available tools."""
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{BASE}tools/registry/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("web_search", resp.data)

    def test_seed_action(self):
        """POST seed/ creates tool entries for all registry tools."""
        self.client.force_authenticate(self.user)
        resp = self.client.post(f"{BASE}tools/seed/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("total", resp.data)

    def test_enabled_action(self):
        """GET enabled/ returns enabled + approved tools."""
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{BASE}tools/enabled/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


# ======================================================================
# UserAPIKey ViewSet
# ======================================================================


class UserAPIKeyViewSetTests(ChatbotTestMixin, TestCase):
    """Tests for UserAPIKeyViewSet."""

    def setUp(self):
        self.client = APIClient()
        self.user = self.create_user()
        self.admin = self.create_admin_user()
        self.api_key = self.create_api_key(self.user)

    def test_list_api_keys(self):
        """GET list returns user's API keys."""
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{BASE}api-keys/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_create_api_key(self):
        """POST stores a new API key (encrypted)."""
        self.client.force_authenticate(self.user)
        resp = self.client.post(f"{BASE}api-keys/", {
            "provider": "anthropic",
            "key_name": "My Claude Key",
            "api_key": "sk-ant-api03-long-fake-key-for-testing-12345",
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        # Response should NOT contain the raw key
        self.assertNotIn("api_key", resp.data)
        self.assertIn("display_key", resp.data)

    def test_retrieve_key_no_raw(self):
        """Retrieve never exposes the raw key."""
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{BASE}api-keys/{self.api_key.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertNotIn("encrypted_key", resp.data)
        self.assertIn("display_key", resp.data)

    def test_set_default_action(self):
        """POST set-default/ sets key as default."""
        self.client.force_authenticate(self.user)
        resp = self.client.post(f"{BASE}api-keys/{self.api_key.id}/set-default/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.api_key.refresh_from_db()
        self.assertTrue(self.api_key.is_default)

    def test_deactivate_action(self):
        """POST deactivate/ soft-deletes the key."""
        self.client.force_authenticate(self.user)
        resp = self.client.post(f"{BASE}api-keys/{self.api_key.id}/deactivate/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.api_key.refresh_from_db()
        self.assertFalse(self.api_key.is_active)

    def test_providers_action(self):
        """GET providers/ lists user's active providers."""
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{BASE}api-keys/providers/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("providers", resp.data)

    def test_usage_summary_action(self):
        """GET usage-summary/ returns aggregated key usage."""
        self.client.force_authenticate(self.user)
        resp = self.client.get(f"{BASE}api-keys/usage-summary/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("total_keys", resp.data)


# ======================================================================
# Schema Generation Tests
# ======================================================================


class ChatbotSchemaGenerationTests(ChatbotTestMixin, TestCase):
    """Tests that drf-spectacular schema generation doesn't crash."""

    def _make_viewset(self, viewset_class):
        """Create a viewset instance with swagger_fake_view set."""
        viewset = viewset_class()
        viewset.swagger_fake_view = True
        viewset.request = None
        viewset.format_kwarg = None
        return viewset

    def test_chat_session_swagger(self):
        from chatbot.api.views import ChatSessionViewSet
        qs = self._make_viewset(ChatSessionViewSet).get_queryset()
        self.assertEqual(qs.count(), 0)

    def test_preference_swagger(self):
        from chatbot.api.views import UserPreferenceViewSet
        qs = self._make_viewset(UserPreferenceViewSet).get_queryset()
        self.assertEqual(qs.count(), 0)

    def test_token_usage_swagger(self):
        from chatbot.api.views import TokenUsageViewSet
        qs = self._make_viewset(TokenUsageViewSet).get_queryset()
        self.assertEqual(qs.count(), 0)

    def test_feedback_swagger(self):
        from chatbot.api.views import MessageFeedbackViewSet
        qs = self._make_viewset(MessageFeedbackViewSet).get_queryset()
        self.assertEqual(qs.count(), 0)

    def test_document_swagger(self):
        from chatbot.api.views import UserDocumentViewSet
        qs = self._make_viewset(UserDocumentViewSet).get_queryset()
        self.assertEqual(qs.count(), 0)

    def test_system_prompt_swagger(self):
        from chatbot.api.views import SystemPromptViewSet
        qs = self._make_viewset(SystemPromptViewSet).get_queryset()
        self.assertEqual(qs.count(), 0)

    def test_tool_swagger(self):
        from chatbot.api.views import UserToolViewSet
        qs = self._make_viewset(UserToolViewSet).get_queryset()
        self.assertEqual(qs.count(), 0)

    def test_api_key_swagger(self):
        from chatbot.api.views import UserAPIKeyViewSet
        qs = self._make_viewset(UserAPIKeyViewSet).get_queryset()
        self.assertEqual(qs.count(), 0)

    def test_chat_session_serializer_dispatch(self):
        """get_serializer_class() returns the right serializer per action."""
        from chatbot.api.views import ChatSessionViewSet
        from chatbot.api.serializers import (
            ChatSessionListSerializer,
            ChatSessionCreateSerializer,
            ChatSessionUpdateSerializer,
            ChatSessionSerializer,
        )

        vs = ChatSessionViewSet()

        vs.action = "list"
        self.assertEqual(vs.get_serializer_class(), ChatSessionListSerializer)

        vs.action = "create"
        self.assertEqual(vs.get_serializer_class(), ChatSessionCreateSerializer)

        vs.action = "partial_update"
        self.assertEqual(vs.get_serializer_class(), ChatSessionUpdateSerializer)

        vs.action = "retrieve"
        self.assertEqual(vs.get_serializer_class(), ChatSessionSerializer)
