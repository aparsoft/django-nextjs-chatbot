"""
Django admin configuration for SystemPromptTemplate model.

Provides a comprehensive admin interface for managing reusable
system prompt templates, including activation, default management,
duplication, and usage analytics.

Design principles:
  - Model methods are preferred over re-implementing logic in admin.
  - Admin-specific display helpers live here since they are
    presentation-only and don't belong on the model.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.db import models
from django.forms import Textarea

from ..models import SystemPromptTemplate


# ---------------------------------------------------------------------------
# Custom filters
# ---------------------------------------------------------------------------


class PromptStatusFilter(admin.SimpleListFilter):
    """Filter prompts by combined status (active, inactive, default)."""

    title = _("Status")
    parameter_name = "prompt_status"

    def lookups(self, request, model_admin):
        return [
            ("active", _("Active")),
            ("inactive", _("Inactive")),
            ("default", _("Default")),
            ("public", _("Public")),
        ]

    def queryset(self, request, queryset):
        if self.value() == "active":
            return queryset.filter(is_active=True)
        if self.value() == "inactive":
            return queryset.filter(is_active=False)
        if self.value() == "default":
            return queryset.filter(is_default=True)
        if self.value() == "public":
            return queryset.filter(is_public=True)
        return queryset


# ---------------------------------------------------------------------------
# Admin configuration
# ---------------------------------------------------------------------------


@admin.register(SystemPromptTemplate)
class SystemPromptTemplateAdmin(admin.ModelAdmin):
    """
    Admin configuration for SystemPromptTemplate model.

    Organised for template management: list view surfaces key metadata
    and status; detail view groups fields logically; actions delegate
    to model methods for state changes and duplication.
    """

    # ---- List display ----
    list_display = (
        "name",
        "category_display",
        "is_default_display",
        "is_active_display",
        "is_public_display",
        "usage_count",
        "average_rating_display",
        "has_variables_display",
        "updated_at",
    )

    list_display_links = ("name",)

    list_filter = (
        "category",
        PromptStatusFilter,
        "is_active",
        "is_public",
        "is_default",
        "recommended_model",
        "created_at",
    )

    search_fields = (
        "name",
        "slug",
        "content",
        "description",
    )

    ordering = ("-is_default", "-usage_count", "name")

    date_hierarchy = "created_at"

    readonly_fields = (
        "usage_count",
        "average_rating_display",
        "rating_count",
        "rating_sum",
        "unfilled_variables_display",
        "created_at",
        "updated_at",
    )

    prepopulated_fields = {"slug": ("name",)}

    # ---- Fieldsets ----
    fieldsets = (
        (
            _("Identification"),
            {
                "fields": (
                    "name",
                    "slug",
                    "category",
                ),
            },
        ),
        (
            _("Content"),
            {
                "fields": (
                    "content",
                    "description",
                ),
            },
        ),
        (
            _("Variables"),
            {
                "fields": (
                    "variables",
                    "example_variables",
                    "unfilled_variables_display",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Recommended Settings"),
            {
                "fields": (
                    "recommended_model",
                    "recommended_temperature",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Visibility & Status"),
            {
                "fields": (
                    "is_default",
                    "is_active",
                    "is_public",
                ),
            },
        ),
        (
            _("Tags"),
            {
                "fields": ("tags",),
                "classes": ("collapse",),
            },
        ),
        (
            _("Analytics"),
            {
                "fields": (
                    "usage_count",
                    "average_rating_display",
                    "rating_count",
                    "rating_sum",
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
        models.TextField: {"widget": Textarea(attrs={"rows": 8, "cols": 100})},
    }

    # ---- Actions ----
    actions = [
        "action_activate",
        "action_deactivate",
        "action_set_default",
        "action_unset_default",
        "action_make_public",
        "action_make_private",
        "action_duplicate",
    ]

    # ------------------------------------------------------------------
    # Display helpers (admin-specific, not on the model)
    # ------------------------------------------------------------------

    @admin.display(description=_("Category"), ordering="category")
    def category_display(self, obj):
        """Show human-readable category label."""
        return obj.get_category_display()

    @admin.display(description=_("Default"), boolean=True)
    def is_default_display(self, obj):
        """Show default status as a boolean icon."""
        return obj.is_default

    @admin.display(description=_("Active"), boolean=True)
    def is_active_display(self, obj):
        """Show active status as a boolean icon."""
        return obj.is_active

    @admin.display(description=_("Public"), boolean=True)
    def is_public_display(self, obj):
        """Show public status as a boolean icon."""
        return obj.is_public

    @admin.display(description=_("Avg Rating"), ordering="rating_sum")
    def average_rating_display(self, obj):
        """Show average rating using the model's average_rating property."""
        avg = obj.average_rating
        if obj.rating_count == 0:
            return "—"
        return f"{avg:.1f} ★ ({obj.rating_count})"

    @admin.display(description=_("Variables"), boolean=True)
    def has_variables_display(self, obj):
        """Show whether template uses variables, using the model property."""
        return obj.has_variables

    @admin.display(description=_("Unfilled Variables"))
    def unfilled_variables_display(self, obj):
        """
        Show variable placeholders found in the content.

        Uses the model's get_unfilled_variables() method directly.
        """
        unfilled = obj.get_unfilled_variables()
        if not unfilled:
            return _("No variables found in content.")
        return ", ".join(f"{{{v}}}" for v in sorted(unfilled))

    # ------------------------------------------------------------------
    # Actions — delegate to model methods or direct field updates
    # ------------------------------------------------------------------

    def action_activate(self, request, queryset):
        """Activate selected templates."""
        updated = queryset.update(is_active=True)
        self.message_user(
            request, _("%(count)d template(s) activated.") % {"count": updated}
        )

    action_activate.short_description = _("Activate selected templates")

    def action_deactivate(self, request, queryset):
        """
        Deactivate selected templates.

        Prevents deactivating the default template to avoid losing
        the platform's fallback prompt.
        """
        default_in_qs = queryset.filter(is_default=True)
        if default_in_qs.exists():
            self.message_user(
                request,
                _("Cannot deactivate the default template. Unset default first."),
                level="WARNING",
            )
            return

        updated = queryset.update(is_active=False)
        self.message_user(
            request, _("%(count)d template(s) deactivated.") % {"count": updated}
        )

    action_deactivate.short_description = _("Deactivate selected templates")

    def action_set_default(self, request, queryset):
        """
        Set the selected template as the default.

        Only one template can be the default, so this unsets any
        existing default first. Only a single template should be
        selected for this action.
        """
        if queryset.count() != 1:
            self.message_user(
                request,
                _("Select exactly one template to set as default."),
                level="WARNING",
            )
            return

        # Unset existing default
        SystemPromptTemplate.objects.filter(is_default=True).update(is_default=False)

        template = queryset.first()
        template.is_default = True
        template.is_active = True  # Default must be active
        template.save(update_fields=["is_default", "is_active"])

        self.message_user(
            request,
            _('"%(name)s" is now the default template.') % {"name": template.name},
        )

    action_set_default.short_description = _("Set as default template")

    def action_unset_default(self, request, queryset):
        """Remove default status from selected templates."""
        updated = queryset.filter(is_default=True).update(is_default=False)
        self.message_user(
            request,
            _("%(count)d template(s) had default status removed.") % {"count": updated},
        )

    action_unset_default.short_description = _("Remove default status")

    def action_make_public(self, request, queryset):
        """Make selected templates publicly available."""
        updated = queryset.update(is_public=True)
        self.message_user(
            request,
            _("%(count)d template(s) made public.") % {"count": updated},
        )

    action_make_public.short_description = _("Make public")

    def action_make_private(self, request, queryset):
        """Make selected templates private."""
        updated = queryset.update(is_public=False)
        self.message_user(
            request,
            _("%(count)d template(s) made private.") % {"count": updated},
        )

    action_make_private.short_description = _("Make private")

    def action_duplicate(self, request, queryset):
        """
        Duplicate selected templates.

        Uses the model's duplicate() method which copies content,
        category, tags, variables, and recommended settings while
        resetting is_default and is_public flags.
        """
        count = 0
        for template in queryset:
            template.duplicate()
            count += 1
        self.message_user(
            request,
            _("%(count)d template(s) duplicated.") % {"count": count},
        )

    action_duplicate.short_description = _("Duplicate selected templates")
