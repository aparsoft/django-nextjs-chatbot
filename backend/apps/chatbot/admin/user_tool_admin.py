"""
Django admin configuration for UserTool model.

Provides a comprehensive admin interface for managing user-enabled
tools/functions, including approval workflows, activation, and
rate limit management.

Design principles:
  - Model methods are preferred over re-implementing logic in admin.
  - Admin-specific display helpers live here since they are
    presentation-only and don't belong on the model.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.db import models
from django.forms import Textarea

from ..models import UserTool, TOOL_REGISTRY


# ---------------------------------------------------------------------------
# Custom filters
# ---------------------------------------------------------------------------


class ToolCategoryFilter(admin.SimpleListFilter):
    """Filter tools by category."""

    title = _("Category")
    parameter_name = "category"

    def lookups(self, request, model_admin):
        return UserTool._meta.get_field("category").choices

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(category=self.value())
        return queryset


class ToolApprovalFilter(admin.SimpleListFilter):
    """Filter tools by approval status."""

    title = _("Approval")
    parameter_name = "approval_status"

    def lookups(self, request, model_admin):
        return [
            ("approved", _("Approved")),
            ("pending", _("Pending Approval")),
            ("requires_approval", _("Requires Approval")),
        ]

    def queryset(self, request, queryset):
        if self.value() == "approved":
            return queryset.filter(is_approved=True)
        if self.value() == "pending":
            return queryset.filter(requires_approval=True, is_approved=False)
        if self.value() == "requires_approval":
            return queryset.filter(requires_approval=True)
        return queryset


class RegistryToolFilter(admin.SimpleListFilter):
    """Filter by whether the tool exists in TOOL_REGISTRY."""

    title = _("In Registry")
    parameter_name = "in_registry"

    def lookups(self, request, model_admin):
        return [
            ("yes", _("In Registry")),
            ("no", _("Not In Registry")),
        ]

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(tool_name__in=TOOL_REGISTRY.keys())
        if self.value() == "no":
            return queryset.exclude(tool_name__in=TOOL_REGISTRY.keys())
        return queryset


# ---------------------------------------------------------------------------
# Admin configuration
# ---------------------------------------------------------------------------


@admin.register(UserTool)
class UserToolAdmin(admin.ModelAdmin):
    """
    Admin configuration for UserTool model.

    Organised for tool management: list view surfaces activation and
    approval status; detail view groups fields logically; actions
    delegate to model methods for state transitions.
    """

    # ---- List display ----
    list_display = (
        "tool_display_name",
        "user_email_display",
        "category_display",
        "icon_display",
        "is_enabled_display",
        "is_approved_display",
        "usage_count",
        "rate_limit_display",
        "last_used_at",
        "updated_at",
    )

    list_display_links = ("tool_display_name",)

    list_filter = (
        "is_enabled",
        ToolCategoryFilter,
        ToolApprovalFilter,
        RegistryToolFilter,
        "rate_limit_period",
        "updated_at",
    )

    search_fields = (
        "user__email",
        "user__username",
        "tool_name",
        "tool_display_name",
        "description",
    )

    ordering = ("tool_display_name",)

    readonly_fields = (
        "tool_name",
        "effective_config_display",
        "registry_info_display",
        "approved_by",
        "approved_at",
        "created_at",
        "updated_at",
    )

    # ---- Fieldsets ----
    fieldsets = (
        (
            _("Tool Identification"),
            {
                "fields": (
                    "user",
                    "tool_name",
                    "tool_display_name",
                    "description",
                    "category",
                    "icon",
                ),
            },
        ),
        (
            _("Status"),
            {
                "fields": (
                    "is_enabled",
                    "requires_approval",
                    "is_approved",
                    "approved_by",
                    "approved_at",
                ),
            },
        ),
        (
            _("Configuration"),
            {
                "fields": (
                    "configuration",
                    "effective_config_display",
                ),
            },
        ),
        (
            _("Rate Limiting"),
            {
                "fields": (
                    "rate_limit",
                    "rate_limit_period",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Usage"),
            {
                "fields": (
                    "usage_count",
                    "last_used_at",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Registry Info"),
            {
                "fields": ("registry_info_display",),
                "classes": ("collapse",),
                "description": _(
                    "Information from TOOL_REGISTRY about this tool. "
                    "If the tool is not in the registry, it may be a legacy entry."
                ),
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
        "action_activate",
        "action_deactivate",
        "action_approve",
        "action_reset_usage",
        "action_seed_missing_tools",
    ]

    # ---- Select related for performance ----
    list_select_related = ("user",)
    select_related = ("user", "approved_by")

    # ------------------------------------------------------------------
    # Display helpers (admin-specific, not on the model)
    # ------------------------------------------------------------------

    @admin.display(description=_("User"))
    def user_email_display(self, obj):
        """Show user email for quick identification."""
        return obj.user.email

    @admin.display(description=_("Category"), ordering="category")
    def category_display(self, obj):
        """Show human-readable category label."""
        return obj.get_category_display()

    @admin.display(description=_("Icon"))
    def icon_display(self, obj):
        """Show the tool's emoji icon."""
        return obj.icon or "—"

    @admin.display(description=_("Enabled"), boolean=True)
    def is_enabled_display(self, obj):
        """Show enabled status as a boolean icon."""
        return obj.is_enabled

    @admin.display(description=_("Approved"), boolean=True)
    def is_approved_display(self, obj):
        """Show approval status as a boolean icon."""
        return obj.is_approved

    @admin.display(description=_("Rate Limit"))
    def rate_limit_display(self, obj):
        """Show rate limit in a human-readable format."""
        if obj.rate_limit is None:
            return "∞"
        period = obj.get_rate_limit_period_display()
        return f"{obj.rate_limit}/{period}"

    @admin.display(description=_("Effective Config"))
    def effective_config_display(self, obj):
        """
        Show the merged configuration using the model's method.

        Uses get_effective_config() which merges TOOL_REGISTRY defaults
        with user overrides — user overrides take precedence.
        """
        config = obj.get_effective_config()
        if not config:
            return _("No configuration.")
        lines = []
        for key, value in config.items():
            lines.append(f"{key}: {value}")
        return "\n".join(lines)

    effective_config_display.allow_tags = True

    @admin.display(description=_("Registry Info"))
    def registry_info_display(self, obj):
        """
        Show TOOL_REGISTRY entry for this tool, if it exists.

        Helps admins understand the source-of-truth defaults and
        identify orphaned tools that are no longer in the registry.
        """
        entry = TOOL_REGISTRY.get(obj.tool_name)
        if not entry:
            return _(
                "⚠️ Tool not found in TOOL_REGISTRY. "
                "This may be a legacy or custom entry."
            )

        lines = [
            f"Display name: {entry.get('display_name', 'N/A')}",
            f"Description: {entry.get('description', 'N/A')}",
            f"Category: {entry.get('category', 'N/A')}",
            f"Icon: {entry.get('icon', 'N/A')}",
            f"Default config: {entry.get('default_config', {})}",
        ]
        return "\n".join(lines)

    registry_info_display.allow_tags = True

    # ------------------------------------------------------------------
    # Actions — delegate to model methods
    # ------------------------------------------------------------------

    def action_activate(self, request, queryset):
        """
        Enable selected tools for their users.

        Uses the model's activate() method.
        """
        count = 0
        for tool in queryset:
            tool.activate()
            count += 1
        self.message_user(
            request,
            _("%(count)d tool(s) activated.") % {"count": count},
        )

    action_activate.short_description = _("Activate selected tools")

    def action_deactivate(self, request, queryset):
        """
        Disable selected tools for their users.

        Uses the model's deactivate() method.
        """
        count = 0
        for tool in queryset:
            tool.deactivate()
            count += 1
        self.message_user(
            request,
            _("%(count)d tool(s) deactivated.") % {"count": count},
        )

    action_deactivate.short_description = _("Deactivate selected tools")

    def action_approve(self, request, queryset):
        """
        Approve selected tools that require approval.

        Uses the model's approve() method which records the
        approving admin and timestamp.
        """
        count = 0
        for tool in queryset.filter(requires_approval=True, is_approved=False):
            tool.approve(approved_by_user=request.user)
            count += 1
        self.message_user(
            request,
            _("%(count)d tool(s) approved.") % {"count": count},
        )

    action_approve.short_description = _("Approve pending tools")

    def action_reset_usage(self, request, queryset):
        """
        Reset usage counters for selected tools.

        Uses the model's reset_usage() method.
        """
        count = 0
        for tool in queryset:
            tool.reset_usage()
            count += 1
        self.message_user(
            request,
            _("%(count)d tool(s) usage counters reset.") % {"count": count},
        )

    action_reset_usage.short_description = _("Reset usage counters")

    def action_seed_missing_tools(self, request, queryset):
        """
        Seed any missing TOOL_REGISTRY entries for the selected users.

        Uses the model's seed_all_tools() class method which creates
        UserTool entries for every tool in TOOL_REGISTRY that the user
        doesn't already have.
        """
        user_ids = queryset.values_list("user_id", flat=True).distinct()
        from accounts.models import CustomUser

        users = CustomUser.objects.filter(id__in=user_ids)
        total_seeded = 0

        for user in users:
            results = UserTool.seed_all_tools(user)
            new_count = sum(1 for _, created in results if created)
            total_seeded += new_count

        self.message_user(
            request,
            _("%(count)d new tool(s) seeded across %(users)d user(s).")
            % {"count": total_seeded, "users": users.count()},
        )

    action_seed_missing_tools.short_description = _(
        "Seed missing registry tools for users"
    )
