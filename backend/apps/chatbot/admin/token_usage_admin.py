"""
Django admin configuration for TokenUsage model.

Provides a comprehensive admin interface for monitoring AI token
consumption, cost tracking, and usage analytics.

Design principles:
  - Model methods are preferred over re-implementing logic in admin.
  - Service layer (TokenUsageService) is used for operations that
    require limit checks or cross-model aggregation.
  - Admin-specific display helpers live here since they are
    presentation-only and don't belong on the model.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.db import models
from django.forms import Textarea

from ..models import TokenUsage
from ..services.token_usage_service import TokenUsageService


# ---------------------------------------------------------------------------
# Custom filters
# ---------------------------------------------------------------------------


class CostTierFilter(admin.SimpleListFilter):
    """Filter usage records by cost tier."""

    title = _("Cost Tier")
    parameter_name = "cost_tier"

    def lookups(self, request, model_admin):
        return [
            ("free", _("Free ($0)")),
            ("low", _("Low (< $0.01)")),
            ("medium", _("Medium ($0.01–$0.10)")),
            ("high", _("High ($0.10–$1.00)")),
            ("premium", _("Premium (> $1.00)")),
        ]

    def queryset(self, request, queryset):
        if self.value() == "free":
            return queryset.filter(total_cost=0)
        if self.value() == "low":
            return queryset.filter(total_cost__gt=0, total_cost__lt=0.01)
        if self.value() == "medium":
            return queryset.filter(total_cost__gte=0.01, total_cost__lte=0.10)
        if self.value() == "high":
            return queryset.filter(total_cost__gt=0.10, total_cost__lte=1.00)
        if self.value() == "premium":
            return queryset.filter(total_cost__gt=1.00)
        return queryset


class ErrorStatusFilter(admin.SimpleListFilter):
    """Filter by whether the request had an error."""

    title = _("Error Status")
    parameter_name = "error_status"

    def lookups(self, request, model_admin):
        return [
            ("success", _("Successful")),
            ("error", _("Had Error")),
        ]

    def queryset(self, request, queryset):
        if self.value() == "success":
            return queryset.filter(had_error=False)
        if self.value() == "error":
            return queryset.filter(had_error=True)
        return queryset


# ---------------------------------------------------------------------------
# Admin configuration
# ---------------------------------------------------------------------------


@admin.register(TokenUsage)
class TokenUsageAdmin(admin.ModelAdmin):
    """
    Admin configuration for TokenUsage model.

    Optimised for cost monitoring: list view surfaces token counts,
    costs, and model info; detail view groups fields logically;
    actions leverage the service layer for aggregated analytics.
    """

    # ---- List display ----
    list_display = (
        "short_id_display",
        "user_email_display",
        "session_title_display",
        "model_name",
        "request_type_display",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "total_cost_display",
        "response_time_display",
        "had_error_display",
        "created_at",
    )

    list_display_links = ("short_id_display",)

    list_filter = (
        "model_name",
        "request_type",
        "was_cached",
        ErrorStatusFilter,
        CostTierFilter,
        "created_at",
    )

    search_fields = (
        "user__email",
        "user__username",
        "chat_session__title",
        "chat_session__id",
        "model_name",
        "endpoint",
        "error_message",
    )

    ordering = ("-created_at",)

    date_hierarchy = "created_at"

    readonly_fields = (
        "total_tokens",
        "total_cost",
        "created_at",
        "updated_at",
        "user_usage_summary_display",
    )

    # ---- Fieldsets ----
    fieldsets = (
        (
            _("Association"),
            {
                "fields": (
                    "user",
                    "chat_session",
                ),
            },
        ),
        (
            _("Model & Request"),
            {
                "fields": (
                    "model_name",
                    "request_type",
                    "endpoint",
                ),
            },
        ),
        (
            _("Token Counts"),
            {
                "fields": (
                    "prompt_tokens",
                    "completion_tokens",
                    "reasoning_tokens",
                    "total_tokens",
                ),
            },
        ),
        (
            _("Cost"),
            {
                "fields": (
                    "prompt_cost",
                    "completion_cost",
                    "total_cost",
                ),
            },
        ),
        (
            _("Performance"),
            {
                "fields": (
                    "response_time_ms",
                    "was_cached",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Error Tracking"),
            {
                "fields": (
                    "had_error",
                    "error_message",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("User Usage Summary"),
            {
                "fields": ("user_usage_summary_display",),
                "classes": ("collapse",),
            },
        ),
        (
            _("Additional Data"),
            {
                "fields": ("metadata",),
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
        "action_export_user_stats",
    ]

    # ---- Select related for performance ----
    list_select_related = ("user", "chat_session")
    select_related = ("user", "chat_session")

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
        if obj.chat_session:
            return obj.chat_session.title_preview
        return "—"

    @admin.display(description=_("Type"))
    def request_type_display(self, obj):
        """Show human-readable request type label."""
        return obj.get_request_type_display()

    @admin.display(description=_("Total Cost"), ordering="total_cost")
    def total_cost_display(self, obj):
        """Show total cost formatted as USD."""
        return f"${obj.total_cost:.6f}"

    @admin.display(description=_("Response Time"))
    def response_time_display(self, obj):
        """Show response time in a human-readable format."""
        if obj.response_time_ms is None:
            return "—"
        if obj.response_time_ms >= 1000:
            return f"{obj.response_time_ms / 1000:.1f}s"
        return f"{obj.response_time_ms}ms"

    @admin.display(description=_("Error"), boolean=True)
    def had_error_display(self, obj):
        """Show error status as a boolean icon."""
        return obj.had_error

    @admin.display(description=_("User Usage Summary (30d)"))
    def user_usage_summary_display(self, obj):
        """
        Show aggregated usage stats for the user over the last 30 days.

        Uses TokenUsageService.get_user_usage_stats() which handles
        cross-model aggregation and averaging.
        """
        stats = TokenUsageService.get_user_usage_stats(user=obj.user, days=30)

        lines = [
            f"Period: {stats['period_days']} days",
            f"Total requests: {stats['total_requests']}",
            f"Total tokens: {stats['total_tokens']:,}",
            f"Total cost: ${stats['total_cost']:.4f}",
            f"Avg tokens/request: {stats['avg_tokens_per_request']:.0f}",
            f"Avg response time: {stats['avg_response_time_ms']:.0f}ms",
        ]

        if stats["usage_by_model"]:
            lines.append("")
            lines.append("Breakdown by model:")
            for model_stat in stats["usage_by_model"]:
                lines.append(
                    f"  {model_stat['model_name']}: "
                    f"{model_stat['tokens']:,} tokens, "
                    f"${float(model_stat['cost']):.4f}, "
                    f"{model_stat['requests']} requests"
                )

        return "\n".join(lines)

    user_usage_summary_display.allow_tags = True

    # ------------------------------------------------------------------
    # Actions — delegate to service layer
    # ------------------------------------------------------------------

    def action_export_user_stats(self, request, queryset):
        """
        Export 30-day usage statistics for the users in the selection.

        Uses TokenUsageService.get_user_usage_stats() for each
        distinct user found in the queryset.
        """
        user_ids = queryset.values_list("user_id", flat=True).distinct()
        from accounts.models import CustomUser

        users = CustomUser.objects.filter(id__in=user_ids)
        count = 0
        for user in users:
            stats = TokenUsageService.get_user_usage_stats(user=user, days=30)
            count += 1
            # Log to admin messages for visibility
            self.message_user(
                request,
                _(
                    "%(email)s: %(tokens)s tokens, $%(cost).4f, "
                    "%(requests)d requests (30d)"
                )
                % {
                    "email": user.email,
                    "tokens": f"{stats['total_tokens']:,}",
                    "cost": stats["total_cost"],
                    "requests": stats["total_requests"],
                },
            )

        if count == 0:
            self.message_user(request, _("No users found in selection."))

    action_export_user_stats.short_description = _("Export 30-day usage stats per user")
