"""
Django admin configuration for MessageFeedback model.

Provides a comprehensive admin interface for reviewing and managing
user feedback on AI-generated messages, including review workflows,
escalation, and satisfaction analytics.

Design principles:
  - Model methods are preferred over re-implementing logic in admin.
  - Admin-specific display helpers live here since they are
    presentation-only and don't belong on the model.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.db import models
from django.forms import Textarea

from ..models import MessageFeedback


# ---------------------------------------------------------------------------
# Custom filters
# ---------------------------------------------------------------------------


class FeedbackSentimentFilter(admin.SimpleListFilter):
    """Filter feedback by sentiment (positive, neutral, negative)."""

    title = _("Sentiment")
    parameter_name = "sentiment"

    def lookups(self, request, model_admin):
        return [
            ("positive", _("Positive")),
            ("neutral", _("Neutral")),
            ("negative", _("Negative")),
        ]

    def queryset(self, request, queryset):
        if self.value() == "positive":
            return queryset.filter(
                rating__in=["thumbs_up", "excellent", "good"]
            )
        if self.value() == "neutral":
            return queryset.filter(rating="neutral")
        if self.value() == "negative":
            return queryset.filter(
                rating__in=["thumbs_down", "poor", "very_poor"]
            )
        return queryset


class IssueReportedFilter(admin.SimpleListFilter):
    """Filter feedback by whether an issue was reported."""

    title = _("Issue Reported")
    parameter_name = "has_issue"

    def lookups(self, request, model_admin):
        return [
            ("yes", _("Has Issue")),
            ("no", _("No Issue")),
        ]

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(reported_issue__isnull=False).exclude(
                reported_issue=""
            )
        if self.value() == "no":
            return queryset.filter(
                models.Q(reported_issue__isnull=True)
                | models.Q(reported_issue="")
            )
        return queryset


# ---------------------------------------------------------------------------
# Admin configuration
# ---------------------------------------------------------------------------


@admin.register(MessageFeedback)
class MessageFeedbackAdmin(admin.ModelAdmin):
    """
    Admin configuration for MessageFeedback model.

    Optimised for the admin review workflow: unreviewed feedback is
    surfaced first, actions delegate to model methods, and analytics
    from class methods are displayed in read-only sections.
    """

    # ---- List display ----
    list_display = (
        "short_id_display",
        "user_email_display",
        "session_title_display",
        "rating_display",
        "sentiment_icon_display",
        "reported_issue",
        "reviewed_display",
        "action_taken",
        "created_at",
    )

    list_display_links = ("short_id_display",)

    list_filter = (
        "rating",
        FeedbackSentimentFilter,
        "reviewed",
        "action_taken",
        "reported_issue",
        IssueReportedFilter,
        "model_used",
        "created_at",
    )

    search_fields = (
        "user__email",
        "user__username",
        "chat_session__title",
        "checkpoint_id",
        "feedback_text",
        "admin_notes",
    )

    ordering = ("reviewed", "-created_at")

    date_hierarchy = "created_at"

    readonly_fields = (
        "created_at",
        "updated_at",
        "sentiment_score_display",
        "satisfaction_summary_display",
    )

    # ---- Fieldsets ----
    fieldsets = (
        (
            _("Feedback Details"),
            {
                "fields": (
                    "user",
                    "chat_session",
                    "checkpoint_id",
                    "message_index",
                    "rating",
                    "sentiment_score_display",
                ),
            },
        ),
        (
            _("Feedback Content"),
            {
                "fields": (
                    "feedback_text",
                    "feedback_categories",
                    "message_preview",
                ),
            },
        ),
        (
            _("Issue Report"),
            {
                "fields": (
                    "reported_issue",
                    "model_used",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Admin Review"),
            {
                "fields": (
                    "reviewed",
                    "reviewed_by",
                    "reviewed_at",
                    "action_taken",
                    "admin_notes",
                ),
            },
        ),
        (
            _("Analytics"),
            {
                "fields": (
                    "satisfaction_summary_display",
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
        "action_mark_reviewed",
        "action_mark_noted",
        "action_escalate",
        "action_mark_fixed",
        "action_notify_user",
    ]

    # ---- Select related for performance ----
    list_select_related = ("user", "chat_session")
    select_related = ("user", "chat_session", "reviewed_by")

    # ------------------------------------------------------------------
    # Display helpers (admin-specific, not on the model)
    # ------------------------------------------------------------------

    @admin.display(description=_("ID"))
    def short_id_display(self, obj):
        """Show truncated ID for compact list view."""
        return str(obj.id)[:8] + "…"

    @admin.display(description=_("User"))
    def user_email_display(self, obj):
        """Show user email for quick identification."""
        return obj.user.email

    @admin.display(description=_("Session"))
    def session_title_display(self, obj):
        """Show chat session title using the model's title_preview property."""
        return obj.chat_session.title_preview

    @admin.display(description=_("Rating"))
    def rating_display(self, obj):
        """Show human-readable rating label."""
        return obj.get_rating_display()

    @admin.display(description=_("Sentiment"))
    def sentiment_icon_display(self, obj):
        """Show sentiment as a visual icon using the model's properties."""
        if obj.is_positive:
            return "👍"
        if obj.is_negative:
            return "👎"
        return "😐"

    @admin.display(description=_("Reviewed"), boolean=True)
    def reviewed_display(self, obj):
        """Show review status as a boolean icon."""
        return obj.reviewed

    @admin.display(description=_("Sentiment Score"))
    def sentiment_score_display(self, obj):
        """
        Show the numeric sentiment score from the model property.

        Uses the model's sentiment_score property directly.
        """
        score = obj.sentiment_score
        if score > 0:
            return f"+{score} (Positive)"
        if score < 0:
            return f"{score} (Negative)"
        return "0 (Neutral)"

    @admin.display(description=_("Session Satisfaction"))
    def satisfaction_summary_display(self, obj):
        """
        Show satisfaction metrics for the related chat session.

        Uses the model's get_session_satisfaction() class method.
        """
        satisfaction = MessageFeedback.get_session_satisfaction(obj.chat_session)
        if satisfaction["total"] == 0:
            return _("No feedback data for this session.")

        lines = [
            f"Total feedback: {satisfaction['total']}",
            f"Positive: {satisfaction['positive']}",
            f"Negative: {satisfaction['negative']}",
            f"Neutral: {satisfaction['neutral']}",
            f"Satisfaction rate: {satisfaction['satisfaction_rate']:.1f}%",
        ]
        return "\n".join(lines)

    satisfaction_summary_display.allow_tags = True

    # ------------------------------------------------------------------
    # Actions — delegate to model methods
    # ------------------------------------------------------------------

    def action_mark_reviewed(self, request, queryset):
        """
        Mark selected feedback as reviewed.

        Uses the model's mark_reviewed() method.
        """
        count = 0
        for feedback in queryset:
            feedback.mark_reviewed(
                reviewer=request.user,
                action_taken="noted",
            )
            count += 1
        self.message_user(
            request, _("%(count)d feedback item(s) marked as reviewed.") % {"count": count}
        )

    action_mark_reviewed.short_description = _("Mark as reviewed")

    def action_mark_noted(self, request, queryset):
        """
        Mark selected feedback as noted for training.

        Uses the model's mark_reviewed() method with action_taken='noted'.
        """
        count = 0
        for feedback in queryset:
            feedback.mark_reviewed(
                reviewer=request.user,
                action_taken="noted",
            )
            count += 1
        self.message_user(
            request, _("%(count)d feedback item(s) noted for training.") % {"count": count}
        )

    action_mark_noted.short_description = _("Mark as noted for training")

    def action_escalate(self, request, queryset):
        """
        Escalate selected feedback for urgent review.

        Uses the model's escalate() method.
        """
        count = 0
        for feedback in queryset:
            feedback.escalate(escalated_by=request.user)
            count += 1
        self.message_user(
            request, _("%(count)d feedback item(s) escalated.") % {"count": count}
        )

    action_escalate.short_description = _("Escalate selected feedback")

    def action_mark_fixed(self, request, queryset):
        """
        Mark the issue as fixed for selected feedback.

        Uses the model's mark_reviewed() method with action_taken='fixed'.
        """
        count = 0
        for feedback in queryset:
            feedback.mark_reviewed(
                reviewer=request.user,
                action_taken="fixed",
            )
            count += 1
        self.message_user(
            request, _("%(count)d feedback item(s) marked as fixed.") % {"count": count}
        )

    action_mark_fixed.short_description = _("Mark issue as fixed")

    def action_notify_user(self, request, queryset):
        """
        Mark that the user has been notified about the action taken.

        Uses the model's mark_reviewed() method with
        action_taken='user_notified'.
        """
        count = 0
        for feedback in queryset:
            feedback.mark_reviewed(
                reviewer=request.user,
                action_taken="user_notified",
            )
            count += 1
        self.message_user(
            request,
            _("%(count)d feedback item(s) marked as user notified.") % {"count": count},
        )

    action_notify_user.short_description = _("Mark user as notified")