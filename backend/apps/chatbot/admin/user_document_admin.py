"""
Django admin configuration for UserDocument model.

Provides a comprehensive admin interface for managing user-uploaded
documents for RAG, including processing status tracking, retry
actions, and storage analytics.

Design principles:
  - Model methods are preferred over re-implementing logic in admin.
  - Service layer (DocumentProcessingService) is used for operations
    that involve text extraction, chunking, or embedding management.
  - Admin-specific display helpers live here since they are
    presentation-only and don't belong on the model.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.db import models
from django.forms import Textarea

from ..models import UserDocument
from ..services.document_processing_service import DocumentProcessingService


# ---------------------------------------------------------------------------
# Custom filters
# ---------------------------------------------------------------------------


class ProcessingStatusFilter(admin.SimpleListFilter):
    """Filter documents by processing status group."""

    title = _("Processing Status")
    parameter_name = "processing_group"

    def lookups(self, request, model_admin):
        return [
            ("pending", _("Pending")),
            ("in_progress", _("In Progress")),
            ("done", _("Completed")),
            ("failed", _("Failed")),
            ("retryable", _("Failed & Retryable")),
        ]

    def queryset(self, request, queryset):
        if self.value() == "pending":
            return queryset.filter(processing_status=UserDocument.STATUS_PENDING)
        if self.value() == "in_progress":
            return queryset.filter(processing_status=UserDocument.STATUS_PROCESSING)
        if self.value() == "done":
            return queryset.filter(processing_status=UserDocument.STATUS_COMPLETED)
        if self.value() == "failed":
            return queryset.filter(processing_status=UserDocument.STATUS_FAILED)
        if self.value() == "retryable":
            return queryset.filter(
                processing_status=UserDocument.STATUS_FAILED,
                retry_count__lt=UserDocument.MAX_RETRIES,
            )
        return queryset


class FileSizeFilter(admin.SimpleListFilter):
    """Filter documents by file size range."""

    title = _("File Size")
    parameter_name = "file_size_range"

    def lookups(self, request, model_admin):
        return [
            ("small", _("< 1 MB")),
            ("medium", _("1–10 MB")),
            ("large", _("10–50 MB")),
            ("huge", _("> 50 MB")),
        ]

    def queryset(self, request, queryset):
        if self.value() == "small":
            return queryset.filter(file_size__lt=1024 * 1024)
        if self.value() == "medium":
            return queryset.filter(
                file_size__gte=1024 * 1024, file_size__lt=10 * 1024 * 1024
            )
        if self.value() == "large":
            return queryset.filter(
                file_size__gte=10 * 1024 * 1024, file_size__lt=50 * 1024 * 1024
            )
        if self.value() == "huge":
            return queryset.filter(file_size__gte=50 * 1024 * 1024)
        return queryset


class EmbeddingStatusFilter(admin.SimpleListFilter):
    """Filter by whether document has embeddings."""

    title = _("Embeddings")
    parameter_name = "has_embeddings"

    def lookups(self, request, model_admin):
        return [
            ("yes", _("Has Embeddings")),
            ("no", _("No Embeddings")),
        ]

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(
                processing_status=UserDocument.STATUS_COMPLETED,
                vector_collection_name__isnull=False,
            ).exclude(vector_collection_name="")
        if self.value() == "no":
            return queryset.filter(
                models.Q(vector_collection_name__isnull=True)
                | models.Q(vector_collection_name="")
                | ~models.Q(processing_status=UserDocument.STATUS_COMPLETED)
            )
        return queryset


# ---------------------------------------------------------------------------
# Admin configuration
# ---------------------------------------------------------------------------


@admin.register(UserDocument)
class UserDocumentAdmin(admin.ModelAdmin):
    """
    Admin configuration for UserDocument model.

    Optimised for document processing management: list view surfaces
    processing status and file metadata; detail view groups fields
    logically; actions delegate to model methods for state transitions
    and the service layer for reprocessing.
    """

    # ---- List display ----
    list_display = (
        "file_name_display",
        "user_email_display",
        "session_title_display",
        "file_size_display",
        "file_type_display",
        "processing_status_display",
        "chunk_count",
        "has_embeddings_display",
        "is_active_display",
        "created_at",
    )

    list_display_links = ("file_name_display",)

    list_filter = (
        ProcessingStatusFilter,
        "file_type",
        FileSizeFilter,
        EmbeddingStatusFilter,
        "is_active",
        "is_shared",
        "created_at",
    )

    search_fields = (
        "user__email",
        "user__username",
        "file_name",
        "title",
        "description",
        "vector_collection_name",
    )

    ordering = ("-created_at",)

    date_hierarchy = "created_at"

    readonly_fields = (
        "file_name",
        "file_size",
        "file_size_display",
        "file_type",
        "file_extension",
        "processing_status",
        "processed_at",
        "chunk_count",
        "vector_collection_name",
        "vector_store_ids",
        "retry_count",
        "processing_error",
        "has_embeddings_display",
        "storage_usage_display",
        "processing_stats_display",
        "created_at",
        "updated_at",
    )

    # ---- Fieldsets ----
    fieldsets = (
        (
            _("File Information"),
            {
                "fields": (
                    "user",
                    "chat_session",
                    "file",
                    "file_name",
                    "file_size_display",
                    "file_type",
                    "file_extension",
                ),
            },
        ),
        (
            _("Document Metadata"),
            {
                "fields": (
                    "title",
                    "description",
                    "tags",
                    "extracted_metadata",
                    "page_count",
                    "word_count",
                ),
            },
        ),
        (
            _("Processing Status"),
            {
                "fields": (
                    "processing_status",
                    "processed_at",
                    "chunk_count",
                    "has_embeddings_display",
                    "retry_count",
                    "processing_error",
                ),
            },
        ),
        (
            _("Vector Store"),
            {
                "fields": (
                    "vector_collection_name",
                    "vector_store_ids",
                    "vector_collection_metadata",
                    "vector_metadata",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Visibility & Sharing"),
            {
                "fields": (
                    "is_active",
                    "is_shared",
                    "share_settings",
                ),
            },
        ),
        (
            _("Storage & Processing Analytics"),
            {
                "fields": (
                    "storage_usage_display",
                    "processing_stats_display",
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
        "action_retry_processing",
        "action_deactivate",
        "action_reactivate",
    ]

    # ---- Select related for performance ----
    list_select_related = ("user", "chat_session")
    select_related = ("user", "chat_session")

    # ------------------------------------------------------------------
    # Display helpers (admin-specific, not on the model)
    # ------------------------------------------------------------------

    @admin.display(description=_("File Name"), ordering="file_name")
    def file_name_display(self, obj):
        """Show file name, truncated if too long."""
        if len(obj.file_name) <= 40:
            return obj.file_name
        return obj.file_name[:37] + "..."

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

    @admin.display(description=_("Size"), ordering="file_size")
    def file_size_display(self, obj):
        """Show human-readable file size using the model's property."""
        return obj.file_size_display

    @admin.display(description=_("Type"))
    def file_type_display(self, obj):
        """Show file extension as a compact label."""
        return obj.file_extension.upper().lstrip(".")

    @admin.display(description=_("Status"), ordering="processing_status")
    def processing_status_display(self, obj):
        """Show human-readable processing status."""
        status_labels = {
            UserDocument.STATUS_PENDING: "⏳ Pending",
            UserDocument.STATUS_PROCESSING: "🔄 Processing",
            UserDocument.STATUS_COMPLETED: "✅ Completed",
            UserDocument.STATUS_FAILED: "❌ Failed",
        }
        return status_labels.get(obj.processing_status, obj.processing_status)

    @admin.display(description=_("Embeddings"), boolean=True)
    def has_embeddings_display(self, obj):
        """Show embedding status using the model's property."""
        return obj.has_embeddings

    @admin.display(description=_("Active"), boolean=True)
    def is_active_display(self, obj):
        """Show active status as a boolean icon."""
        return obj.is_active

    @admin.display(description=_("User Storage Usage"))
    def storage_usage_display(self, obj):
        """
        Show aggregated storage usage for the document's user.

        Uses the model's get_user_storage_usage() class method.
        """
        usage = UserDocument.get_user_storage_usage(obj.user)

        lines = [
            f"Total documents: {usage['total_documents']}",
            f"Total size: {usage['total_size_mb']} MB",
            f"Total chunks: {usage['total_chunks']}",
        ]
        return "\n".join(lines)

    storage_usage_display.allow_tags = True

    @admin.display(description=_("Processing Stats"))
    def processing_stats_display(self, obj):
        """
        Show platform-wide processing statistics.

        Uses the model's get_processing_stats() class method.
        """
        stats = UserDocument.get_processing_stats()

        lines = [
            f"Total: {stats['total']}",
            f"Pending: {stats['pending']}",
            f"Processing: {stats['processing']}",
            f"Completed: {stats['completed']}",
            f"Failed: {stats['failed']}",
        ]
        return "\n".join(lines)

    processing_stats_display.allow_tags = True

    # ------------------------------------------------------------------
    # Actions — delegate to model methods or service layer
    # ------------------------------------------------------------------

    def action_retry_processing(self, request, queryset):
        """
        Retry processing for failed documents.

        Uses the model's retry_processing() method which checks
        retry_count against MAX_RETRIES and resets status to pending.
        Only documents that can_retry_processing() are affected.
        """
        retried = 0
        skipped = 0
        for doc in queryset:
            if doc.can_retry_processing():
                if doc.retry_processing():
                    retried += 1
                else:
                    skipped += 1
            else:
                skipped += 1

        if retried:
            self.message_user(
                request,
                _("%(count)d document(s) queued for retry.") % {"count": retried},
            )
        if skipped:
            self.message_user(
                request,
                _("%(count)d document(s) skipped (max retries exceeded).")
                % {"count": skipped},
                level="WARNING",
            )

    action_retry_processing.short_description = _(
        "Retry processing for failed documents"
    )

    def action_deactivate(self, request, queryset):
        """
        Deactivate selected documents.

        Uses the model's deactivate() method which soft-deletes
        (hides from search but keeps data).
        """
        count = 0
        for doc in queryset:
            doc.deactivate()
            count += 1
        self.message_user(
            request,
            _("%(count)d document(s) deactivated.") % {"count": count},
        )

    action_deactivate.short_description = _("Deactivate selected documents")

    def action_reactivate(self, request, queryset):
        """
        Reactivate selected documents.

        Uses the model's reactivate() method.
        """
        count = 0
        for doc in queryset:
            doc.reactivate()
            count += 1
        self.message_user(
            request,
            _("%(count)d document(s) reactivated.") % {"count": count},
        )

    action_reactivate.short_description = _("Reactivate selected documents")
