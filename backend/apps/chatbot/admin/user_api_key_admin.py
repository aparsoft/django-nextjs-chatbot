"""
Django admin configuration for UserAPIKey model.

Provides a comprehensive admin interface for managing encrypted
user API keys, including validation, rotation, default management,
and usage analytics.

Design principles:
  - Model methods are preferred over re-implementing logic in admin.
  - Service layer (APIKeyService) is used for operations that
    require permission checks or cross-key default management.
  - Admin-specific display helpers live here since they are
    presentation-only and don't belong on the model.
  - Encrypted keys are NEVER exposed in the admin interface.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.db import models
from django.forms import Textarea

from ..models import UserAPIKey
from ..services.api_key_service import APIKeyService


# ---------------------------------------------------------------------------
# Custom filters
# ---------------------------------------------------------------------------


class KeyValidationFilter(admin.SimpleListFilter):
    """Filter API keys by validation status."""

    title = _("Validation")
    parameter_name = "validation_status"

    def lookups(self, request, model_admin):
        return [
            ("validated", _("Validated")),
            ("not_validated", _("Not Validated")),
            ("validation_failed", _("Validation Failed")),
        ]

    def queryset(self, request, queryset):
        if self.value() == "validated":
            return queryset.filter(is_validated=True)
        if self.value() == "not_validated":
            return queryset.filter(is_validated=False, validation_error="")
        if self.value() == "validation_failed":
            return queryset.filter(is_validated=False).exclude(
                models.Q(validation_error__isnull=True) | models.Q(validation_error="")
            )
        return queryset


class KeyUsageFilter(admin.SimpleListFilter):
    """Filter API keys by usage level."""

    title = _("Usage Level")
    parameter_name = "usage_level"

    def lookups(self, request, model_admin):
        return [
            ("unused", _("Never Used")),
            ("low", _("Low (< 100 uses)")),
            ("medium", _("Medium (100–1000)")),
            ("high", _("High (> 1000)")),
        ]

    def queryset(self, request, queryset):
        if self.value() == "unused":
            return queryset.filter(usage_count=0)
        if self.value() == "low":
            return queryset.filter(usage_count__gte=1, usage_count__lt=100)
        if self.value() == "medium":
            return queryset.filter(usage_count__gte=100, usage_count__lte=1000)
        if self.value() == "high":
            return queryset.filter(usage_count__gt=1000)
        return queryset


# ---------------------------------------------------------------------------
# Admin configuration
# ---------------------------------------------------------------------------


@admin.register(UserAPIKey)
class UserAPIKeyAdmin(admin.ModelAdmin):
    """
    Admin configuration for UserAPIKey model.

    Security-first design: encrypted keys are never exposed in the
    admin. Display shows masked keys only. Actions delegate to model
    methods for validation, rotation, and deactivation.
    """

    # ---- List display ----
    list_display = (
        "key_name",
        "user_email_display",
        "provider_display",
        "display_key_display",
        "is_active_display",
        "is_default_display",
        "is_validated_display",
        "usage_count",
        "last_used_at",
        "created_at",
    )

    list_display_links = ("key_name",)

    list_filter = (
        "provider",
        "is_active",
        "is_default",
        KeyValidationFilter,
        KeyUsageFilter,
        "created_at",
    )

    search_fields = (
        "user__email",
        "user__username",
        "key_name",
        "key_prefix",
        "provider_display_name",
    )

    ordering = ("-is_default", "-last_used_at", "-created_at")

    date_hierarchy = "created_at"

    readonly_fields = (
        "display_key_display",
        "key_prefix",
        "is_validated",
        "last_validated_at",
        "validation_error",
        "usage_count",
        "last_used_at",
        "total_tokens_used",
        "usage_summary_display",
        "created_at",
        "updated_at",
    )

    # ---- Fieldsets ----
    fieldsets = (
        (
            _("Key Identification"),
            {
                "fields": (
                    "user",
                    "key_name",
                    "provider",
                    "provider_display_name",
                ),
            },
        ),
        (
            _("Key Security"),
            {
                "fields": (
                    "display_key_display",
                    "key_prefix",
                ),
                "description": _(
                    "Encrypted keys are never shown in the admin. "
                    "Only the masked prefix is visible for identification."
                ),
            },
        ),
        (
            _("Status"),
            {
                "fields": (
                    "is_active",
                    "is_default",
                ),
            },
        ),
        (
            _("Validation"),
            {
                "fields": (
                    "is_validated",
                    "last_validated_at",
                    "validation_error",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Usage & Limits"),
            {
                "fields": (
                    "usage_count",
                    "last_used_at",
                    "total_tokens_used",
                    "daily_limit",
                    "monthly_limit",
                ),
            },
        ),
        (
            _("Usage Summary"),
            {
                "fields": ("usage_summary_display",),
                "classes": ("collapse",),
            },
        ),
        (
            _("Provider Configuration"),
            {
                "fields": ("custom_config",),
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
    }

    # ---- Actions ----
    actions = [
        "action_validate_keys",
        "action_deactivate",
        "action_set_default",
        "action_unset_default",
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

    @admin.display(description=_("Provider"), ordering="provider")
    def provider_display(self, obj):
        """Show human-readable provider name using the model's property."""
        return obj.provider_name

    @admin.display(description=_("Key"))
    def display_key_display(self, obj):
        """Show masked key using the model's display_key property."""
        return obj.display_key

    @admin.display(description=_("Active"), boolean=True)
    def is_active_display(self, obj):
        """Show active status as a boolean icon."""
        return obj.is_active

    @admin.display(description=_("Default"), boolean=True)
    def is_default_display(self, obj):
        """Show default status as a boolean icon."""
        return obj.is_default

    @admin.display(description=_("Validated"), boolean=True)
    def is_validated_display(self, obj):
        """Show validation status as a boolean icon."""
        return obj.is_validated

    @admin.display(description=_("Usage Summary"))
    def usage_summary_display(self, obj):
        """
        Show aggregated usage stats for the user across all keys.

        Uses the model's get_usage_summary() class method.
        """
        summary = UserAPIKey.get_usage_summary(obj.user)

        lines = [
            f"Total keys: {summary['total_keys']}",
            f"Active keys: {summary['active_keys']}",
            f"Total tokens used: {summary['total_tokens']:,}",
        ]

        if summary["by_provider"]:
            lines.append("")
            lines.append("Breakdown by provider:")
            for provider_stat in summary["by_provider"]:
                lines.append(
                    f"  {provider_stat['provider']}: "
                    f"{provider_stat['key_count']} key(s), "
                    f"{provider_stat['total_tokens']:,} tokens, "
                    f"{provider_stat['total_usage']} uses"
                )

        return "\n".join(lines)

    usage_summary_display.allow_tags = True

    # ------------------------------------------------------------------
    # Actions — delegate to model methods or service layer
    # ------------------------------------------------------------------

    def action_validate_keys(self, request, queryset):
        """
        Validate selected API keys with their providers.

        Uses the model's validate_key() method which handles
        provider-specific validation and updates is_validated status.
        """
        count = 0
        for key in queryset:
            result = key.validate_key()
            count += 1
            if not result["valid"]:
                self.message_user(
                    request,
                    _("Key '%(name)s' (%(provider)s): validation failed — %(error)s")
                    % {
                        "name": key.key_name,
                        "provider": key.provider_name,
                        "error": result["error"],
                    },
                    level="WARNING",
                )

        self.message_user(
            request,
            _("%(count)d key(s) validation processed.") % {"count": count},
        )

    action_validate_keys.short_description = _("Validate selected keys")

    def action_deactivate(self, request, queryset):
        """
        Deactivate selected API keys.

        Uses the model's deactivate() method.
        """
        count = 0
        for key in queryset:
            key.deactivate()
            count += 1
        self.message_user(
            request,
            _("%(count)d key(s) deactivated.") % {"count": count},
        )

    action_deactivate.short_description = _("Deactivate selected keys")

    def action_set_default(self, request, queryset):
        """
        Set selected key as default for its provider.

        Only one key per provider can be default, so this unsets
        any existing default for the same provider first.
        Uses APIKeyService.set_default_key() which handles the
        cross-key default management atomically.
        """
        if queryset.count() != 1:
            self.message_user(
                request,
                _("Select exactly one key to set as default."),
                level="WARNING",
            )
            return

        key = queryset.first()

        # Use service which handles unsetting other defaults
        APIKeyService.set_default_key(user=key.user, key_id=key.id)

        self.message_user(
            request,
            _('"%(name)s" is now the default key for %(provider)s.')
            % {"name": key.key_name, "provider": key.provider_name},
        )

    action_set_default.short_description = _("Set as default key")

    def action_unset_default(self, request, queryset):
        """Remove default status from selected keys."""
        updated = queryset.filter(is_default=True).update(is_default=False)
        self.message_user(
            request,
            _("%(count)d key(s) had default status removed.") % {"count": updated},
        )

    action_unset_default.short_description = _("Remove default status")

    # ------------------------------------------------------------------
    # Security: prevent exposing encrypted keys
    # ------------------------------------------------------------------

    def get_readonly_fields(self, request, obj=None):
        """
        Ensure encrypted_key binary field is never editable.

        The encrypted_key field is excluded from the form entirely
        via fieldsets, but this adds an extra safety layer.
        """
        readonly = list(self.readonly_fields)
        if obj:
            readonly.append("encrypted_key")
        return readonly

    def has_add_permission(self, request):
        """
        Disable adding API keys through admin.

        API keys should be created through the service layer
        (APIKeyService.create_api_key) which handles encryption
        properly. Direct admin creation would skip encryption.
        """
        return False
