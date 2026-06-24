"""Tests for chatbot models — ChatSession, UserPreference, TokenUsage,
MessageFeedback, UserDocument, SystemPromptTemplate, UserTool, UserAPIKey."""

from django.test import TestCase
from django.db import IntegrityError
from decimal import Decimal

from . import ChatbotTestMixin


# ======================================================================
# ChatSession
# ======================================================================


class ChatSessionModelTests(ChatbotTestMixin, TestCase):
    """Tests for ChatSession model."""

    def setUp(self):
        self.user = self.create_user()
        self.session = self.create_session(self.user)

    # ---- Creation ----

    def test_create_session_defaults(self):
        """Session has correct defaults."""
        self.assertEqual(self.session.title, "Test Session 1")
        self.assertEqual(self.session.model_name, "gpt-4o-mini")
        self.assertEqual(self.session.temperature, 0.7)
        self.assertTrue(self.session.is_active)
        self.assertFalse(self.session.is_archived)
        self.assertFalse(self.session.is_pinned)
        self.assertEqual(self.session.message_count, 0)
        self.assertEqual(self.session.total_tokens_used, 0)

    def test_session_uuid_pk(self):
        """Session uses UUID primary key."""
        from uuid import UUID

        self.assertIsInstance(self.session.pk, UUID)

    def test_str_returns_title_and_email(self):
        """__str__ includes title and user email."""
        self.assertIn(self.session.title, str(self.session))
        self.assertIn(self.user.email, str(self.session))

    # ---- Properties ----

    def test_thread_id_is_string_pk(self):
        """thread_id returns string version of the UUID."""
        self.assertEqual(self.session.thread_id, str(self.session.id))

    def test_is_new_when_no_messages(self):
        """is_new returns True when message_count is 0."""
        self.assertTrue(self.session.is_new)

    def test_is_not_new_after_messages(self):
        """is_new returns False after message_count > 0."""
        self.session.message_count = 5
        self.session.save()
        self.assertFalse(self.session.is_new)

    def test_title_preview_short(self):
        """title_preview returns full title when short."""
        self.session.title = "Short Title"
        self.assertEqual(self.session.title_preview, "Short Title")

    def test_title_preview_long(self):
        """title_preview truncates titles longer than 50 chars."""
        self.session.title = "A" * 60
        preview = self.session.title_preview
        self.assertEqual(len(preview), 50)
        self.assertTrue(preview.endswith("..."))

    # ---- State transitions ----

    def test_archive(self):
        """archive() sets is_archived=True, is_active=False."""
        self.session.archive()
        self.session.refresh_from_db()
        self.assertTrue(self.session.is_archived)
        self.assertFalse(self.session.is_active)

    def test_activate(self):
        """activate() sets is_archived=False, is_active=True."""
        self.session.archive()
        self.session.activate()
        self.session.refresh_from_db()
        self.assertFalse(self.session.is_archived)
        self.assertTrue(self.session.is_active)

    def test_toggle_pin(self):
        """toggle_pin() flips is_pinned."""
        self.assertFalse(self.session.is_pinned)
        self.session.toggle_pin()
        self.session.refresh_from_db()
        self.assertTrue(self.session.is_pinned)
        self.session.toggle_pin()
        self.session.refresh_from_db()
        self.assertFalse(self.session.is_pinned)

    def test_soft_delete(self):
        """soft_delete() archives, deactivates, clears metadata."""
        self.session.tags = ["test"]
        self.session.metadata = {"key": "value"}
        self.session.soft_delete()
        self.session.refresh_from_db()
        self.assertFalse(self.session.is_active)
        self.assertTrue(self.session.is_archived)
        self.assertEqual(self.session.tags, [])
        self.assertEqual(self.session.metadata, {})

    # ---- Analytics ----

    def test_update_analytics(self):
        """update_analytics() increments counters."""
        self.session.update_analytics(message_count=2, tokens_used=150)
        self.session.refresh_from_db()
        self.assertEqual(self.session.message_count, 2)
        self.assertEqual(self.session.total_tokens_used, 150)
        self.assertIsNotNone(self.session.last_message_at)

    def test_update_title(self):
        """update_title() sets title from first message."""
        self.session.update_title("Hello, how are you doing today my friend?")
        self.session.refresh_from_db()
        self.assertNotEqual(self.session.title, "New Conversation")
        self.assertIn("Hello", self.session.title)

    def test_update_title_skips_custom(self):
        """update_title() does not overwrite custom titles."""
        self.session.title = "Custom Title"
        self.session.save()
        self.session.update_title("New message content")
        self.session.refresh_from_db()
        self.assertEqual(self.session.title, "Custom Title")

    # ---- Class methods ----

    def test_get_active_for_user(self):
        """get_active_for_user returns only active sessions."""
        self.create_session(self.user, title="Active")
        archived = self.create_session(self.user, title="Archived")
        archived.archive()
        active = ChatSession.get_active_for_user(self.user) if __debug__ else None
        from chatbot.models import ChatSession

        active = ChatSession.get_active_for_user(self.user)
        self.assertEqual(active.count(), 2)  # self.session + new active

    def test_get_session_stats(self):
        """get_session_stats returns aggregate stats."""
        from chatbot.models import ChatSession

        self.create_session(self.user)
        stats = ChatSession.get_session_stats(self.user)
        self.assertEqual(stats["total_sessions"], 2)
        self.assertEqual(stats["active_count"], 2)


# ======================================================================
# UserPreference
# ======================================================================


class UserPreferenceModelTests(ChatbotTestMixin, TestCase):
    """Tests for UserPreference model."""

    def setUp(self):
        self.user = self.create_user()
        self.prefs = self.create_preference(self.user)

    def test_create_preference_defaults(self):
        """Preference has correct defaults."""
        self.assertEqual(self.prefs.default_model, "gpt-4o-mini")
        self.assertEqual(self.prefs.default_temperature, 0.7)
        self.assertTrue(self.prefs.enable_streaming)
        self.assertEqual(self.prefs.theme, "auto")

    def test_str_returns_email(self):
        """__str__ includes user email."""
        self.assertIn(self.user.email, str(self.prefs))

    def test_has_usage_limits_true(self):
        """has_usage_limits is True when limits > 0."""
        self.prefs.daily_message_limit = 100
        self.prefs.save()
        self.assertTrue(self.prefs.has_usage_limits)

    def test_has_usage_limits_false(self):
        """has_usage_limits is False when limits are 0."""
        self.prefs.daily_message_limit = 0
        self.prefs.daily_token_limit = 0
        self.prefs.save()
        self.assertFalse(self.prefs.has_usage_limits)

    def test_is_dark_mode(self):
        """is_dark_mode returns True when theme is dark."""
        self.prefs.theme = "dark"
        self.assertTrue(self.prefs.is_dark_mode)

    def test_get_session_config(self):
        """get_session_config returns correct dict."""
        config = self.prefs.get_session_config()
        self.assertIn("model_name", config)
        self.assertIn("temperature", config)
        self.assertIn("streaming", config)

    def test_reset_to_defaults(self):
        """reset_to_defaults restores platform defaults."""
        self.prefs.default_model = "gpt-4o"
        self.prefs.default_temperature = 1.5
        self.prefs.save()
        self.prefs.reset_to_defaults()
        self.prefs.refresh_from_db()
        self.assertEqual(self.prefs.default_model, "gpt-4o-mini")
        self.assertEqual(self.prefs.default_temperature, 0.7)

    def test_update_from_dict(self):
        """update_from_dict updates specified fields."""
        self.prefs.update_from_dict(
            {
                "default_model": "gpt-4o",
                "theme": "dark",
            }
        )
        self.prefs.refresh_from_db()
        self.assertEqual(self.prefs.default_model, "gpt-4o")
        self.assertEqual(self.prefs.theme, "dark")

    def test_update_from_dict_ignores_unknown(self):
        """update_from_dict ignores unknown keys."""
        updated = self.prefs.update_from_dict({"nonexistent_field": "value"})
        self.assertNotIn("nonexistent_field", updated)

    def test_get_or_create_for_user(self):
        """get_or_create_for_user is idempotent."""
        from chatbot.models import UserPreference

        prefs1 = UserPreference.get_or_create_for_user(self.user)
        prefs2 = UserPreference.get_or_create_for_user(self.user)
        self.assertEqual(prefs1.id, prefs2.id)

    def test_one_to_one_constraint(self):
        """Cannot create a second preference for the same user."""
        from chatbot.models import UserPreference

        with self.assertRaises(IntegrityError):
            UserPreference.objects.create(user=self.user)


# ======================================================================
# TokenUsage
# ======================================================================


class TokenUsageModelTests(ChatbotTestMixin, TestCase):
    """Tests for TokenUsage model."""

    def setUp(self):
        self.user = self.create_user()
        self.session = self.create_session(self.user)

    def test_create_usage_auto_calculates_totals(self):
        """save() auto-calculates total_tokens and total_cost."""
        usage = self.create_token_usage(
            self.user,
            self.session,
            prompt_tokens=100,
            completion_tokens=50,
            prompt_cost=Decimal("0.000015"),
            completion_cost=Decimal("0.000030"),
        )
        self.assertEqual(usage.total_tokens, 150)
        self.assertEqual(usage.total_cost, Decimal("0.000045"))

    def test_str_returns_usage_info(self):
        """__str__ includes user email, tokens, and cost."""
        usage = self.create_token_usage(self.user, self.session)
        s = str(usage)
        self.assertIn(self.user.email, s)
        self.assertIn("tokens", s)

    def test_calculate_cost(self):
        """calculate_cost returns correct cost dict."""
        from chatbot.models import TokenUsage

        costs = TokenUsage.calculate_cost("gpt-4o-mini", 1000000, 1000000)
        self.assertEqual(costs["prompt_cost"], Decimal("0.15"))
        self.assertEqual(costs["completion_cost"], Decimal("0.60"))

    def test_get_user_usage_today(self):
        """get_user_usage_today returns today's aggregate."""
        from chatbot.models import TokenUsage

        self.create_token_usage(
            self.user, self.session, prompt_tokens=200, completion_tokens=100
        )
        usage = TokenUsage.get_user_usage_today(self.user)
        self.assertEqual(usage["message_count"], 1)
        self.assertGreater(usage["total_tokens"], 0)


# ======================================================================
# MessageFeedback
# ======================================================================


class MessageFeedbackModelTests(ChatbotTestMixin, TestCase):
    """Tests for MessageFeedback model."""

    def setUp(self):
        self.user = self.create_user()
        self.session = self.create_session(self.user)

    def test_create_feedback(self):
        """Feedback is created with correct defaults."""
        fb = self.create_feedback(self.user, self.session)
        self.assertEqual(fb.rating, "thumbs_up")
        self.assertFalse(fb.reviewed)

    def test_is_positive_negative(self):
        """is_positive / is_negative properties work."""
        fb_up = self.create_feedback(self.user, self.session, rating="thumbs_up")
        self.assertTrue(fb_up.is_positive)
        self.assertFalse(fb_up.is_negative)

        fb_down = self.create_feedback(self.user, self.session, rating="thumbs_down")
        self.assertFalse(fb_down.is_positive)
        self.assertTrue(fb_down.is_negative)


# ======================================================================
# UserDocument
# ======================================================================


class UserDocumentModelTests(ChatbotTestMixin, TestCase):
    """Tests for UserDocument model."""

    def setUp(self):
        self.user = self.create_user()
        self.session = self.create_session(self.user)

    def test_create_document(self):
        """Document has correct defaults."""
        doc = self.create_document(self.user, self.session)
        self.assertEqual(doc.processing_status, "pending")
        self.assertTrue(doc.is_active)
        self.assertEqual(doc.retry_count, 0)
        self.assertEqual(doc.chunk_count, 0)

    def test_file_size_mb(self):
        """file_size_mb returns size in megabytes."""
        doc = self.create_document(self.user, self.session, file_size=2 * 1024 * 1024)
        self.assertEqual(doc.file_size_mb, 2.0)

    def test_file_size_display(self):
        """file_size_display returns human-readable string."""
        doc = self.create_document(self.user, self.session, file_size=1500)
        self.assertIn("KB", doc.file_size_display)

    def test_state_transitions(self):
        """Processing status transitions work."""
        doc = self.create_document(self.user, self.session)
        self.assertTrue(doc.is_pending)

        doc.mark_processing_started()
        doc.refresh_from_db()
        self.assertTrue(doc.is_processing)

        doc.mark_processing_completed(
            collection_name="test_collection",
            vector_ids=["id1", "id2"],
            chunk_count=2,
        )
        doc.refresh_from_db()
        self.assertTrue(doc.is_completed)
        self.assertEqual(doc.chunk_count, 2)

    def test_mark_processing_failed(self):
        """Failed processing sets error and increments retry."""
        doc = self.create_document(self.user, self.session)
        doc.mark_processing_failed("OCR failed")
        doc.refresh_from_db()
        self.assertTrue(doc.is_failed)
        self.assertEqual(doc.processing_error, "OCR failed")
        self.assertEqual(doc.retry_count, 1)

    def test_can_retry_processing(self):
        """can_retry_processing respects MAX_RETRIES."""
        doc = self.create_document(self.user, self.session)
        doc.mark_processing_failed("error")
        doc.mark_processing_failed("error")
        doc.mark_processing_failed("error")
        self.assertFalse(doc.can_retry_processing())

    def test_deactivate_reactivate(self):
        """deactivate/reactivate toggle is_active."""
        doc = self.create_document(self.user, self.session)
        doc.deactivate()
        doc.refresh_from_db()
        self.assertFalse(doc.is_active)
        doc.reactivate()
        doc.refresh_from_db()
        self.assertTrue(doc.is_active)

    def test_get_user_storage_usage(self):
        """get_user_storage_usage returns aggregate storage."""
        from chatbot.models import UserDocument

        self.create_document(self.user, self.session, file_size=1024)
        self.create_document(self.user, self.session, file_size=2048)
        usage = UserDocument.get_user_storage_usage(self.user)
        self.assertEqual(usage["total_documents"], 2)
        self.assertEqual(usage["total_size_bytes"], 3072)


# ======================================================================
# SystemPromptTemplate
# ======================================================================


class SystemPromptTemplateModelTests(ChatbotTestMixin, TestCase):
    """Tests for SystemPromptTemplate model."""

    def test_create_template(self):
        """Template has correct defaults."""
        t = self.create_system_prompt()
        self.assertEqual(t.category, "general")
        self.assertTrue(t.is_active)
        self.assertFalse(t.is_default)
        self.assertEqual(t.usage_count, 0)

    def test_str_returns_name(self):
        """__str__ returns the name."""
        t = self.create_system_prompt(name="My Prompt")
        self.assertEqual(str(t), "My Prompt")

    def test_average_rating(self):
        """average_rating calculates correctly."""
        t = self.create_system_prompt()
        self.assertEqual(t.average_rating, 0.0)
        t.add_rating(4)
        t.add_rating(5)
        self.assertEqual(t.average_rating, 4.5)

    def test_add_rating_invalid(self):
        """add_rating rejects values outside 1-5."""
        t = self.create_system_prompt()
        with self.assertRaises(ValueError):
            t.add_rating(0)
        with self.assertRaises(ValueError):
            t.add_rating(6)

    def test_render_with_variables(self):
        """render() replaces placeholders."""
        t = self.create_system_prompt(content="Hello {name}, welcome to {topic}!")
        result = t.render({"name": "Ada", "topic": "Python"})
        self.assertEqual(result, "Hello Ada, welcome to Python!")

    def test_validate_variables(self):
        """validate_variables reports missing/extra."""
        t = self.create_system_prompt(content="Hello {name}!")
        result = t.validate_variables({"name": "Ada"})
        self.assertTrue(result["valid"])
        self.assertEqual(result["missing"], [])

        result = t.validate_variables({})
        self.assertFalse(result["valid"])
        self.assertIn("name", result["missing"])

    def test_increment_usage(self):
        """increment_usage() increases usage_count."""
        t = self.create_system_prompt()
        self.assertEqual(t.usage_count, 0)
        t.increment_usage()
        t.refresh_from_db()
        self.assertEqual(t.usage_count, 1)

    def test_duplicate(self):
        """duplicate() creates a copy with '(Copy)' suffix."""
        t = self.create_system_prompt(name="Original")
        dup = t.duplicate()
        self.assertIn("Copy", dup.name)
        self.assertNotEqual(t.id, dup.id)
        self.assertEqual(dup.content, t.content)
        self.assertFalse(dup.is_default)

    def test_get_default(self):
        """get_default returns the default template."""
        from chatbot.models import SystemPromptTemplate

        t = self.create_system_prompt(is_default=True)
        default = SystemPromptTemplate.get_default()
        self.assertEqual(default.id, t.id)

    def test_slug_must_be_unique(self):
        """Duplicate slug raises IntegrityError."""
        self.create_system_prompt(slug="unique-slug")
        with self.assertRaises(IntegrityError):
            self.create_system_prompt(slug="unique-slug")


# ======================================================================
# UserTool
# ======================================================================


class UserToolModelTests(ChatbotTestMixin, TestCase):
    """Tests for UserTool model."""

    def setUp(self):
        self.user = self.create_user()

    def test_create_tool(self):
        """Tool is created with correct defaults."""
        tool = self.create_user_tool(self.user)
        self.assertTrue(tool.is_enabled)
        self.assertTrue(tool.is_approved)
        self.assertEqual(tool.usage_count, 0)

    def test_activate_deactivate(self):
        """activate/deactivate toggle is_enabled."""
        tool = self.create_user_tool(self.user)
        tool.deactivate()
        tool.refresh_from_db()
        self.assertFalse(tool.is_enabled)
        tool.activate()
        tool.refresh_from_db()
        self.assertTrue(tool.is_enabled)

    def test_increment_usage(self):
        """increment_usage() increases count and sets last_used_at."""
        tool = self.create_user_tool(self.user)
        tool.increment_usage()
        tool.refresh_from_db()
        self.assertEqual(tool.usage_count, 1)
        self.assertIsNotNone(tool.last_used_at)

    def test_get_effective_config(self):
        """get_effective_config merges registry defaults + user overrides."""
        tool = self.create_user_tool(
            self.user,
            tool_name="web_search",
            configuration={"max_results": 10},
        )
        config = tool.get_effective_config()
        self.assertEqual(config["max_results"], 10)

    def test_unique_together_user_tool_name(self):
        """Cannot have duplicate (user, tool_name) pair."""
        self.create_user_tool(self.user, tool_name="web_search")
        with self.assertRaises(IntegrityError):
            self.create_user_tool(self.user, tool_name="web_search")

    def test_enable_tool_from_registry(self):
        """enable_tool() creates from TOOL_REGISTRY."""
        from chatbot.models import UserTool

        tool = UserTool.enable_tool(self.user, "calculator")
        self.assertEqual(tool.tool_name, "calculator")
        self.assertTrue(tool.is_enabled)

    def test_enable_unknown_tool_raises(self):
        """enable_tool() rejects unknown tool names."""
        from chatbot.models import UserTool

        with self.assertRaises(ValueError):
            UserTool.enable_tool(self.user, "nonexistent_tool")


# ======================================================================
# UserAPIKey
# ======================================================================


class UserAPIKeyModelTests(ChatbotTestMixin, TestCase):
    """Tests for UserAPIKey model."""

    def setUp(self):
        self.user = self.create_user()

    def test_create_api_key(self):
        """API key is created with correct defaults."""
        key = self.create_api_key(self.user)
        self.assertEqual(key.provider, "openai")
        self.assertTrue(key.is_active)
        self.assertFalse(key.is_default)
        self.assertEqual(key.usage_count, 0)

    def test_display_key_masks(self):
        """display_key masks the actual key."""
        key = self.create_api_key(self.user)
        display = key.display_key
        self.assertIn("****", display)
        self.assertNotIn("sk-test-fake-key", display)

    def test_provider_name(self):
        """provider_name returns human-readable name."""
        key = self.create_api_key(self.user, provider="anthropic")
        self.assertEqual(key.provider_name, "Anthropic (Claude)")

    def test_has_limits(self):
        """has_limits is True when limits are set."""
        key = self.create_api_key(self.user)
        self.assertFalse(key.has_limits)
        key.daily_limit = 10000
        key.save()
        self.assertTrue(key.has_limits)

    def test_deactivate(self):
        """deactivate() sets is_active=False."""
        key = self.create_api_key(self.user)
        key.deactivate()
        key.refresh_from_db()
        self.assertFalse(key.is_active)

    def test_increment_usage(self):
        """increment_usage() updates counters."""
        key = self.create_api_key(self.user)
        key.increment_usage(tokens_used=500)
        key.refresh_from_db()
        self.assertEqual(key.usage_count, 1)
        self.assertEqual(key.total_tokens_used, 500)
        self.assertIsNotNone(key.last_used_at)

    def test_get_default_key(self):
        """get_default_key returns the default key for a provider."""
        from chatbot.models import UserAPIKey

        key = self.create_api_key(self.user, is_default=True)
        result = UserAPIKey.get_default_key(self.user, "openai")
        self.assertEqual(result.id, key.id)
