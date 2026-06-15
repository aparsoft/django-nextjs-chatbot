"""
User Preference model — per-user AI chatbot defaults and settings.

This module defines :class:`UserPreference`, a ``OneToOneField`` model that
stores every user's default model, temperature, summarization style, UI
theme, usage limits, and privacy toggles.  It also provides the
``PREFERENCE_DEFAULTS`` constant used by :meth:`reset_to_defaults` and
:meth:`get_default_config`.

Key design decisions
--------------------
- **OneToOneField** ensures exactly one preference row per user.
- **``get_or_create_for_user``** class method makes it safe to call from
  anywhere — it creates defaults on first access.
- **``get_session_config``** produces the dict that
  :meth:`ChatSession.create_for_user` consumes, keeping the hand-off
  between preferences and sessions explicit.
- **``get_effective_system_prompt``** resolves prompt priority:
  custom user prompt → template → platform default.

Typical usage
-------------
::

    # First access (creates with defaults)
    prefs = UserPreference.get_or_create_for_user(user)

    # Derive session config
    config = prefs.get_session_config()
    session = ChatSession.create_for_user(user, preferences=prefs)

    # Reset to platform defaults
    prefs.reset_to_defaults()

    # Bulk update from serializer validated_data
    prefs.update_from_dict({"default_model": "gpt-5-nano", "theme": "dark"})

Models defined
--------------
- :class:`UserPreference` — per-user AI settings and session defaults.
"""

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from core.models import TimestampedModel


# Default values used by reset_to_defaults()
PREFERENCE_DEFAULTS = {
    "default_model": "gpt-5-mini",
    "default_temperature": 0.7,
    "default_max_tokens": 2000,
    "enable_auto_summarization": True,
    "summarization_trigger_tokens": 384,
    "max_summary_tokens": 128,
    "summarization_style": "concise",
    "response_language": "en",
    "enable_streaming": True,
    "enable_code_execution": False,
    "daily_message_limit": 100,
    "daily_token_limit": 50000,
    "theme": "auto",
    "show_token_count": False,
    "enable_notifications": True,
    "save_conversation_history": True,
    "allow_data_training": False,
}


class UserPreference(TimestampedModel):
    """
    User-specific AI chatbot preferences and settings.

    Stores default configurations for new chat sessions and
    global user preferences for AI interactions.
    """

    # One preference per user
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_preferences",
        help_text=_("User these preferences belong to"),
    )

    # Default model settings
    default_model = models.CharField(
        max_length=100,
        default="gpt-5-mini",
        choices=[
            ("gpt-5-mini", "GPT-5 Mini (Recommended)"),
            ("gpt-5-nano", "GPT-5 Nano (Smaller/Faster)"),
            ("gpt-4.1-mini", "GPT-4.1 Mini (Faster/Cheaper)"),
            ("gpt-4o-mini", "GPT-4o Mini (Faster/Cheaper)"),
            ("o4-mini", "GPT-o4 Mini (Reasoning)"),
        ],
        help_text=_("Default AI model for new conversations"),
    )

    default_temperature = models.FloatField(
        default=0.7,
        help_text=_("Default temperature (0.0-2.0). Higher = more creative"),
    )

    default_max_tokens = models.IntegerField(
        default=2000, help_text=_("Default max tokens for responses")
    )

    # Summarization preferences
    enable_auto_summarization = models.BooleanField(
        default=True, help_text=_("Enable automatic conversation summarization")
    )

    summarization_trigger_tokens = models.IntegerField(
        default=384, help_text=_("Token count to trigger summarization")
    )

    max_summary_tokens = models.IntegerField(
        default=128, help_text=_("Maximum tokens in summary")
    )

    summarization_style = models.CharField(
        max_length=20,
        default="concise",
        choices=[
            ("concise", "Concise (Brief summaries)"),
            ("detailed", "Detailed (More context)"),
            ("bullet", "Bullet Points"),
        ],
        help_text=_("Style of automatic summaries"),
    )

    # System prompt
    custom_system_prompt = models.TextField(
        blank=True, null=True, help_text=_("Custom system prompt for all conversations")
    )

    use_custom_system_prompt = models.BooleanField(
        default=False, help_text=_("Use custom system prompt instead of default")
    )

    # Response preferences
    response_language = models.CharField(
        max_length=10,
        default="en",
        help_text=_("Preferred response language code (e.g., en, es, fr)"),
    )

    enable_streaming = models.BooleanField(
        default=True, help_text=_("Enable streaming responses (word-by-word)")
    )

    enable_code_execution = models.BooleanField(
        default=False, help_text=_("Allow AI to execute code (advanced users only)")
    )

    # Usage limits
    daily_message_limit = models.IntegerField(
        default=100, help_text=_("Maximum messages per day (0 = unlimited)")
    )

    daily_token_limit = models.IntegerField(
        default=50000, help_text=_("Maximum tokens per day (0 = unlimited)")
    )

    # UI preferences
    theme = models.CharField(
        max_length=20,
        default="auto",
        choices=[
            ("light", "Light Theme"),
            ("dark", "Dark Theme"),
            ("auto", "Auto (System)"),
        ],
        help_text=_("Chat interface theme"),
    )

    show_token_count = models.BooleanField(
        default=False, help_text=_("Show token count in chat interface")
    )

    enable_notifications = models.BooleanField(
        default=True, help_text=_("Enable browser notifications for AI responses")
    )

    # Privacy settings
    save_conversation_history = models.BooleanField(
        default=True, help_text=_("Save conversation history for future reference")
    )

    allow_data_training = models.BooleanField(
        default=False,
        help_text=_("Allow conversations to be used for model improvement"),
    )

    # Advanced settings
    additional_settings = models.JSONField(
        default=dict, blank=True, help_text=_("Additional user-specific settings")
    )

    class Meta:
        verbose_name = _("User Preference")
        verbose_name_plural = _("User Preferences")

    def __str__(self):
        return f"Preferences for {self.user.email}"

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def has_usage_limits(self):
        """Check if user has any usage limits set."""
        return self.daily_message_limit > 0 or self.daily_token_limit > 0

    @property
    def is_dark_mode(self):
        """Check if user explicitly prefers dark mode."""
        return self.theme == "dark"

    @property
    def is_light_mode(self):
        """Check if user explicitly prefers light mode."""
        return self.theme == "light"

    # ------------------------------------------------------------------
    # Instance methods
    # ------------------------------------------------------------------

    def get_session_config(self):
        """
        Get configuration dict for new chat sessions.

        Returns:
            dict: Configuration for ChatSession and LangGraph
        """
        return {
            "model_name": self.default_model,
            "temperature": self.default_temperature,
            "max_tokens": self.default_max_tokens,
            "enable_summarization": self.enable_auto_summarization,
            "summarization_threshold": self.summarization_trigger_tokens,
            "max_summary_tokens": self.max_summary_tokens,
            "system_prompt": (
                self.custom_system_prompt if self.use_custom_system_prompt else None
            ),
            "language": self.response_language,
            "streaming": self.enable_streaming,
        }

    def get_effective_system_prompt(self, template=None):
        """
        Return the system prompt to actually use.

        Priority:
            1. User's custom prompt (if use_custom_system_prompt is True)
            2. Provided SystemPromptTemplate (if any)
            3. Platform default

        Args:
            template: Optional SystemPromptTemplate instance

        Returns:
            str: The system prompt to send to the LLM
        """
        if self.use_custom_system_prompt and self.custom_system_prompt:
            return self.custom_system_prompt

        if template:
            return template.render(
                {"user_name": self.user.get_full_name() or self.user.email}
            )

        # Platform default
        return (
            "You are a helpful, friendly AI assistant. "
            "Be concise and clear in your responses."
        )

    def reset_to_defaults(self):
        """
        Reset all preferences to platform defaults.

        Keeps user relationship and additional_settings intact.
        """
        for field, value in PREFERENCE_DEFAULTS.items():
            setattr(self, field, value)
        self.custom_system_prompt = None
        self.use_custom_system_prompt = False
        self.save()

    def update_from_dict(self, data):
        """
        Bulk-update preferences from a validated dict.

        Only updates fields that exist on the model and are present in data.
        Ignores unknown keys — safe to pass raw serializer validated_data.

        Args:
            data: dict of field_name -> value

        Returns:
            list of fields that were updated
        """
        model_fields = {f.name for f in self._meta.get_fields()}
        updated_fields = []

        for key, value in data.items():
            if key in model_fields and key not in ("id", "user"):
                setattr(self, key, value)
                updated_fields.append(key)

        if updated_fields:
            self.save(update_fields=updated_fields)

        return updated_fields

    def to_display_dict(self):
        """
        Return a serializable dict of preferences for API responses.

        Converts non-JSON-safe types (like Decimals) to native types.
        """
        return {
            "default_model": self.default_model,
            "default_temperature": self.default_temperature,
            "default_max_tokens": self.default_max_tokens,
            "enable_auto_summarization": self.enable_auto_summarization,
            "summarization_style": self.summarization_style,
            "use_custom_system_prompt": self.use_custom_system_prompt,
            "has_custom_prompt": bool(self.custom_system_prompt),
            "response_language": self.response_language,
            "enable_streaming": self.enable_streaming,
            "theme": self.theme,
            "has_usage_limits": self.has_usage_limits,
            "daily_message_limit": self.daily_message_limit,
            "daily_token_limit": self.daily_token_limit,
        }

    # ------------------------------------------------------------------
    # Class methods
    # ------------------------------------------------------------------

    @classmethod
    def get_or_create_for_user(cls, user):
        """
        Get existing preferences or create with defaults.

        Safe to call repeatedly — returns the same object.
        """
        preferences, created = cls.objects.get_or_create(user=user)
        return preferences

    @classmethod
    def get_default_config(cls):
        """
        Return the platform-default config (no DB query needed).

        Useful when user doesn't exist yet (e.g., anonymous preview).
        """
        return {
            "model_name": PREFERENCE_DEFAULTS["default_model"],
            "temperature": PREFERENCE_DEFAULTS["default_temperature"],
            "max_tokens": PREFERENCE_DEFAULTS["default_max_tokens"],
            "enable_summarization": PREFERENCE_DEFAULTS["enable_auto_summarization"],
            "summarization_threshold": PREFERENCE_DEFAULTS["summarization_trigger_tokens"],
            "streaming": PREFERENCE_DEFAULTS["enable_streaming"],
            "language": PREFERENCE_DEFAULTS["response_language"],
        }
