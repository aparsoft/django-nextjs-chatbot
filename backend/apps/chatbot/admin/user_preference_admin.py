"""
Django admin configuration for UserPreference model.

Provides a comprehensive admin interface for managing user AI
chatbot preferences and settings, including session config
preview and bulk reset actions.

Design principles:
  - Model methods are preferred over re-implementing logic in admin.
  - Admin-specific display helpers live here since they are
    presentation-only and don't belong on the model.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.db import models
from django.forms import Textarea

from ..models import UserPreference


# ---------------------------------------------------------------------------
# Custom filters
# ---------------------------------------------------------------------------


class ModelChoiceFilter(admin.SimpleListFilter):
    """Filter preferences by default model choice."""

    title = _("Default Model")
    parameter_name = "default_model"

    def lookups(self, request, model_admin):
        return UserPreference._meta.get_field("default_model").choices

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(default_model=self.value())
        return queryset


class ThemeFilter(admin.SimpleListFilter):
    """Filter preferences by theme choice."""

    title = _("Theme")
    parameter_name = "theme"

    def lookups(self, request, model_admin):
        return UserPreference._meta.get_field("theme").choices

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(theme=self.value())
        return queryset


class UsageLimitFilter(admin.SimpleListFilter):
    """Filter by whether user has usage limits configured."""

    title = _("Usage Limits")
    parameter_name = "has_limits"

    def lookups(self, request, model_admin):
        return [
            ("limited", _("Has Limits")),
            ("unlimited", _("No Limits")),
        ]

    def queryset(self, request, queryset):
        if self.value() == "limited":
            return queryset.filter(
                models.Q(daily_message_limit__gt=0) | models.Q(daily_token_limit__gt=0)
            )
        if self.value() == "unlimited":
            return queryset.filter(daily_message_limit=0, daily_token_limit=0)
        return queryset


# ---------------------------------------------------------------------------
# Admin configuration
# ---------------------------------------------------------------------------


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    """
    Admin configuration for UserPreference model.

    Organised for quick inspection of user settings: list view
    surfaces key defaults; detail view groups fields into logical
    sections matching the preference categories users see.
    """

    # ---- List display ----
    list_display = (
        "user_email_display",
        "default_model_display",
        "default_temperature",
        "summarization_style_display",
        "streaming_display",
        "theme_display",
        "has_limits_display",
        "updated_at",
    )

    list_display_links = ("user_email_display",)

    list_filter = (
        ModelChoiceFilter,
        ThemeFilter,
        UsageLimitFilter,
        "enable_auto_summarization",
        "use_custom_system_prompt",
        "enable_streaming",
        "enable_code_execution",
        "allow_data_training",
        "save_conversation_history",
    )

    search_fields = (
        "user__email",
        "user__username",
        "user__first_name",
        "user__last_name",
    )

    ordering = ("-updated_at",)

    readonly_fields = (
        "user",
        "session_config_display",
        "effective_prompt_display",
        "created_at",
        "updated_at",
    )

    # ---- Fieldsets ----
    fieldsets = (
        (
            _("User"),
            {
                "fields": ("user",),
            },
        ),
        (
            _("Default Model Settings"),
            {
                "fields": (
                    "default_model",
                    "default_temperature",
                    "default_max_tokens",
                ),
            },
        ),
        (
            _("Summarization"),
            {
                "fields": (
                    "enable_auto_summarization",
                    "summarization_trigger_tokens",
                    "max_summary_tokens",
                    "summarization_style",
                ),
            },
        ),
        (
            _("System Prompt"),
            {
                "fields": (
                    "use_custom_system_prompt",
                    "custom_system_prompt",
                    "effective_prompt_display",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Response Preferences"),
            {
                "fields": (
                    "response_language",
                    "enable_streaming",
                    "enable_code_execution",
                ),
            },
        ),
        (
            _("Usage Limits"),
            {
                "fields": (
                    "daily_message_limit",
                    "daily_token_limit",
                ),
            },
        ),
        (
            _("UI Preferences"),
            {
                "fields": (
                    "theme",
                    "show_token_count",
                    "enable_notifications",
                ),
            },
        ),
        (
            _("Privacy"),
            {
                "fields": (
                    "save_conversation_history",
                    "allow_data_training",
                ),
            },
        ),
        (
            _("Session Config Preview"),
            {
                "fields": ("session_config_display",),
                "classes": ("collapse",),
                "description": _(
                    "Configuration dict that will be applied to new chat sessions."
                ),
            },
        ),
        (
            _("Advanced"),
            {
                "fields": ("additional_settings",),
                "classes": ("collapse",),
            },
        ),
        (
            _("Timestamps"),
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    # ---- Form overrides ----
    formfield_overrides = {
        models.JSONField: {"widget": Textarea(attrs={"rows": 4, "cols": 80})},
        models.TextField: {"widget": Textarea(attrs={"rows": 4, "cols": 80})},
    }

    # ---- Actions ----
    actions = [
        "action_reset_to_defaults",
        "action_enable_summarization",
        "action_disable_summarization",
        "action_enable_streaming",
        "action_disable_streaming",
    ]

    # ---- Select related for performance ----
    list_select_related = ("user",)
    select_related = ("user",)

    # ------------------------------------------------------------------
    # Display helpers (admin-specific, not on the model)
    # ------------------------------------------------------------------

    @admin.display(description=_("User"))
    def user_email_display(self, obj):
        """Show user email for quick identification."""
        return obj.user.email

    @admin.display(description=_("Model"), ordering="default_model")
    def default_model_display(self, obj):
        """Show human-readable model label."""
        return obj.get_default_model_display()

    @admin.display(description=_("Summary Style"))
    def summarization_style_display(self, obj):
        """Show human-readable summarization style label."""
        return obj.get_summarization_style_display()

    @admin.display(description=_("Streaming"), boolean=True)
    def streaming_display(self, obj):
        """Show streaming status as a boolean icon."""
        return obj.enable_streaming

    @admin.display(description=_("Theme"), ordering="theme")
    def theme_display(self, obj):
        """Show human-readable theme label."""
        return obj.get_theme_display()

    @admin.display(description=_("Limits"), boolean=True)
    def has_limits_display(self, obj):
        """Show whether user has limits using the model's property."""
        return obj.has_usage_limits

    @admin.display(description=_("Session Config"))
    def session_config_display(self, obj):
        """
        Show the session config dict that will be applied to new sessions.

        Uses the model's get_session_config() method directly.
        """
        config = obj.get_session_config()
        lines = []
        for key, value in config.items():
            lines.append(f"{key}: {value}")
        return "\n".join(lines)

    session_config_display.allow_tags = True

    @admin.display(description=_("Effective System Prompt"))
    def effective_prompt_display(self, obj):
        """
        Show the system prompt that will actually be used.

        Uses the model's get_effective_system_prompt() method
        which handles the priority chain (custom → template → default).
        """
        prompt = obj.get_effective_system_prompt()
        if len(prompt) > 500:
            return prompt[:497] + "..."
        return prompt

    # ------------------------------------------------------------------
    # Actions — delegate to model methods
    # ------------------------------------------------------------------

    def action_reset_to_defaults(self, request, queryset):
        """
        Reset selected preferences to platform defaults.

        Uses the model's reset_to_defaults() method which applies
        PREFERENCE_DEFAULTS and clears custom system prompt.
        """
        count = 0
        for pref in queryset:
            pref.reset_to_defaults()
            count += 1
        self.message_user(
            request,
            _("%(count)d preference(s) reset to defaults.") % {"count": count},
        )

    action_reset_to_defaults.short_description = _("Reset to platform defaults")

    def action_enable_summarization(self, request, queryset):
        """Enable auto-summarization for selected users."""
        updated = queryset.update(enable_auto_summarization=True)
        self.message_user(
            request,
            _("%(count)d preference(s) updated — summarization enabled.")
            % {"count": updated},
        )

    action_enable_summarization.short_description = _("Enable auto-summarization")

    def action_disable_summarization(self, request, queryset):
        """Disable auto-summarization for selected users."""
        updated = queryset.update(enable_auto_summarization=False)
        self.message_user(
            request,
            _("%(count)d preference(s) updated — summarization disabled.")
            % {"count": updated},
        )

    action_disable_summarization.short_description = _("Disable auto-summarization")

    def action_enable_streaming(self, request, queryset):
        """Enable streaming for selected users."""
        updated = queryset.update(enable_streaming=True)
        self.message_user(
            request,
            _("%(count)d preference(s) updated — streaming enabled.")
            % {"count": updated},
        )

    action_enable_streaming.short_description = _("Enable streaming")

    def action_disable_streaming(self, request, queryset):
        """Disable streaming for selected users."""
        updated = queryset.update(enable_streaming=False)
        self.message_user(
            request,
            _("%(count)d preference(s) updated — streaming disabled.")
            % {"count": updated},
        )

    action_disable_streaming.short_description = _("Disable streaming")
