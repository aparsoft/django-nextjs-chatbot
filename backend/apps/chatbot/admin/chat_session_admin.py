"""
Django admin configuration for ChatSession model.

Provides a comprehensive admin interface for managing chat sessions,
including list filters, search, custom actions (archive, activate,
toggle pin, soft-delete), and analytics display.

Design principles:
  - Model methods are preferred over re-implementing logic in admin.
  - Service layer (ChatSessionService) is used for operations that
    require permission checks or cache invalidation.
  - Admin-specific display helpers live here since they are
    presentation-only and don't belong on the model.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.db import models
from django.forms import Textarea

from ..models import ChatSession
from ..services.chat_session_service import ChatSessionService


# ---------------------------------------------------------------------------
# Custom filters
# ---------------------------------------------------------------------------


class SessionStatusFilter(admin.SimpleListFilter):
    """Filter sessions by combined status (active, archived, inactive)."""

    title = _("Status")
    parameter_name = "status"

    def lookups(self, request, model_admin):
        return [
            ("active", _("Active")),
            ("archived", _("Archived")),
            ("inactive", _("Inactive")),
        ]

    def queryset(self, request, queryset):
        if self.value() == "active":
            return queryset.filter(is_active=True, is_archived=False)
        if self.value() == "archived":
            return queryset.filter(is_archived=True)
        if self.value() == "inactive":
            return queryset.filter(is_active=False, is_archived=False)
        return queryset


# ---------------------------------------------------------------------------
# Admin configuration
# ---------------------------------------------------------------------------


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    """
    Admin configuration for ChatSession model.

    List view shows key metadata; detail view organises fields into
    logical sections.  Actions delegate to model methods or the
    ChatSessionService where appropriate.
    """

    # ---- List display ----
    list_display = (
        "title_preview_display",
        "user_email_display",
        "model_name",
        "message_count",
        "total_tokens_used",
        "status_badge_display",
        "is_pinned_display",
        "last_message_at",
        "updated_at",
    )

    list_display_links = ("title_preview_display",)

    list_filter = (
        SessionStatusFilter,
        "model_name",
        "enable_summarization",
        "is_pinned",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "title",
        "user__email",
        "user__username",
        "id",
    )

    ordering = ("-is_pinned", "-last_message_at", "-updated_at")

    date_hierarchy = "created_at"

    readonly_fields = (
        "id",
        "thread_id_display",
        "created_at",
        "updated_at",
        "analytics_summary_display",
    )

    # ---- Fieldsets ----
    fieldsets = (
        (
            _("Identification"),
            {
                "fields": (
                    "id",
                    "thread_id_display",
                    "user",
                ),
            },
        ),
        (
            _("Metadata"),
            {
                "fields": (
                    "title",
                    "description",
                ),
            },
        ),
        (
            _("Session Configuration"),
            {
                "fields": (
                    "model_name",
                    "temperature",
                    "enable_summarization",
                    "summarization_threshold",
                ),
            },
        ),
        (
            _("Status & Visibility"),
            {
                "fields": (
                    "is_active",
                    "is_archived",
                    "is_pinned",
                ),
            },
        ),
        (
            _("Analytics"),
            {
                "fields": (
                    "message_count",
                    "total_tokens_used",
                    "last_message_at",
                    "analytics_summary_display",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Additional Data"),
            {
                "fields": (
                    "tags",
                    "metadata",
                ),
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
        models.TextField: {"widget": Textarea(attrs={"rows": 3, "cols": 80})},
    }

    # ---- Actions ----
    actions = [
        "action_archive",
        "action_activate",
        "action_toggle_pin",
        "action_soft_delete",
        "action_cleanup_old_sessions",
    ]

    # ---- Select related for performance ----
    list_select_related = ("user",)
    select_related = ("user",)

    # ------------------------------------------------------------------
    # Display helpers (admin-specific, not on the model)
    # ------------------------------------------------------------------

    @admin.display(description=_("Title"), ordering="title")
    def title_preview_display(self, obj):
        """Show truncated title using the model's title_preview property."""
        return obj.title_preview

    @admin.display(description=_("User"))
    def user_email_display(self, obj):
        """Show user email for quick identification."""
        return obj.user.email

    @admin.display(description=_("Status"), boolean=True)
    def status_badge_display(self, obj):
        """Show active/archived status as a boolean icon."""
        return obj.is_active and not obj.is_archived

    status_badge_display.short_description = _("Active")

    @admin.display(description=_("Pinned"), boolean=True)
    def is_pinned_display(self, obj):
        """Show pin status as a boolean icon."""
        return obj.is_pinned

    @admin.display(description=_("Thread ID"))
    def thread_id_display(self, obj):
        """Show the LangGraph thread_id (UUID as string)."""
        return obj.thread_id

    @admin.display(description=_("Analytics Summary"))
    def analytics_summary_display(self, obj):
        """
        Render the model's get_analytics_summary() as a readable block.

        Uses the model method directly — no duplicate logic here.
        """
        summary = obj.get_analytics_summary()
        if not summary:
            return _("No analytics available.")

        lines = [
            f"Messages: {summary.get('message_count', 0)}",
            f"Tokens: {summary.get('total_tokens', 0)}",
            f"Cost: ${summary.get('total_cost', 0.0):.4f}",
            f"Last message: {summary.get('last_message_at', 'N/A')}",
            f"Active: {summary.get('is_active', False)}",
            f"Archived: {summary.get('is_archived', False)}",
        ]
        return "\n".join(lines)

    analytics_summary_display.allow_tags = True

    # ------------------------------------------------------------------
    # Actions — delegate to model methods or service layer
    # ------------------------------------------------------------------

    def action_archive(self, request, queryset):
        """
        Archive selected sessions.

        Uses the model's archive() method which sets is_archived=True
        and is_active=False in a single save.
        """
        count = 0
        for session in queryset:
            session.archive()
            count += 1
        self.message_user(
            request, _("%(count)d session(s) archived.") % {"count": count}
        )

    action_archive.short_description = _("Archive selected sessions")

    def action_activate(self, request, queryset):
        """
        Reactivate selected archived sessions.

        Uses the model's activate() method.
        """
        count = 0
        for session in queryset:
            session.activate()
            count += 1
        self.message_user(
            request, _("%(count)d session(s) reactivated.") % {"count": count}
        )

    action_activate.short_description = _("Reactivate selected sessions")

    def action_toggle_pin(self, request, queryset):
        """
        Toggle pin status for selected sessions.

        Uses the model's toggle_pin() method.
        """
        count = 0
        for session in queryset:
            session.toggle_pin()
            count += 1
        self.message_user(
            request, _("%(count)d session(s) pin toggled.") % {"count": count}
        )

    action_toggle_pin.short_description = _("Toggle pin for selected sessions")

    def action_soft_delete(self, request, queryset):
        """
        Soft-delete selected sessions.

        Uses the model's soft_delete() method which archives, deactivates,
        and clears sensitive metadata (tags, metadata JSON).
        """
        count = 0
        for session in queryset:
            session.soft_delete()
            count += 1
        self.message_user(
            request,
            _("%(count)d session(s) soft-deleted (archived & metadata cleared).")
            % {"count": count},
        )

    action_soft_delete.short_description = _("Soft-delete selected sessions")

    def action_cleanup_old_sessions(self, request, queryset):
        """
        Archive sessions inactive for 90+ days.

        Delegates to the model's cleanup_old_sessions() class method
        which handles the bulk update efficiently.
        """
        count = ChatSession.cleanup_old_sessions(days_inactive=90)
        self.message_user(
            request, _("%(count)d stale session(s) archived.") % {"count": count}
        )

    action_cleanup_old_sessions.short_description = _(
        "Archive sessions inactive 90+ days"
    )
