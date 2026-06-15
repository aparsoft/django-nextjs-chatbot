"""
User Document model — file uploads for RAG (Retrieval-Augmented Generation).

This module defines :class:`UserDocument`, which tracks user-uploaded files
destined for pgvector embedding.  The model stores **file metadata and
processing state**; the actual vector embeddings live in the
``langchain_pgvector`` database and are referenced by
``vector_collection_name`` and ``vector_store_ids``.

Key design decisions
--------------------
- **State machine** — ``processing_status`` transitions through
  ``pending → processing → completed`` (or ``failed``).  Use
  :meth:`mark_processing_started`, :meth:`mark_processing_completed`, and
  :meth:`mark_processing_failed` to transition; :meth:`can_retry_processing`
  guards against exceeding ``MAX_RETRIES``.
- **Soft delete** — :meth:`deactivate` sets ``is_active=False`` instead of
  deleting the row, preserving analytics and allowing :meth:`reactivate`.
- **Factory method** — :meth:`create_from_upload` extracts metadata from a
  Django ``UploadedFile`` and creates the row in ``pending`` status, ready
  for a Celery task to pick up.
- **pgvector integration** — ``vector_collection_name`` and
  ``vector_store_ids`` are the bridge to LangChain's PGVector store;
  :meth:`get_vector_metadata` produces the filtering dict stored alongside
  each chunk.

Typical usage
-------------
::

    # Upload (in viewset)
    doc = UserDocument.create_from_upload(user, uploaded_file, session=session)

    # Celery task picks it up
    doc.mark_processing_started()
    # ... LangChain embedding pipeline ...
    doc.mark_processing_completed(
        collection_name="user_123_docs",
        vector_ids=["vec1", "vec2"],
        chunk_count=42,
    )

    # Query
    active_docs = UserDocument.get_user_documents(user)
    stats = UserDocument.get_processing_stats(user)

Models defined
--------------
- :class:`UserDocument` — uploaded file metadata with RAG processing state.
"""

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from core.models import TimestampedModel
import os


class UserDocument(TimestampedModel):
    """
    Track user-uploaded documents for RAG.

    The actual embeddings are stored in pgvector (PGVECTOR_CONNECTION_STRING).
    This model stores file metadata and references to vector store.
    """

    # Processing status choices
    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending Processing"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]

    # Maximum retries before giving up
    MAX_RETRIES = 3

    # User and session
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="documents",
        help_text=_("User who uploaded this document"),
    )

    chat_session = models.ForeignKey(
        "chatbot.ChatSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents",
        help_text=_("Chat session this document is associated with"),
    )

    # File information
    file = models.FileField(
        upload_to="user_documents/%Y/%m/%d/", help_text=_("Uploaded document file")
    )

    file_name = models.CharField(max_length=255, help_text=_("Original filename"))

    file_size = models.BigIntegerField(help_text=_("File size in bytes"))

    file_type = models.CharField(max_length=100, help_text=_("MIME type of the file"))

    file_extension = models.CharField(
        max_length=10, help_text=_("File extension (e.g., .pdf, .docx)")
    )

    # Processing status
    processing_status = models.CharField(
        max_length=20,
        default=STATUS_PENDING,
        choices=STATUS_CHOICES,
        help_text=_("Document processing status"),
    )

    processed_at = models.DateTimeField(
        null=True, blank=True, help_text=_("When processing completed")
    )

    # Vector store references - REQUIRED for pgvector
    vector_collection_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True,
        help_text=_(
            "PGVector collection name where embeddings are stored (REQUIRED for vector operations)"
        ),
    )

    vector_collection_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Optional metadata for the PGVector collection itself"),
    )

    vector_store_ids = models.JSONField(
        default=list,
        blank=True,
        help_text=_("List of pgvector document IDs for this file's chunks"),
    )

    chunk_count = models.IntegerField(
        default=0, help_text=_("Number of chunks/embeddings created")
    )

    # Document metadata
    title = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text=_("User-defined or extracted document title"),
    )

    description = models.TextField(
        blank=True, null=True, help_text=_("User description or summary of document")
    )

    tags = models.JSONField(
        default=list, blank=True, help_text=_("User-defined tags for organization")
    )

    # Extracted content metadata (file-level)
    extracted_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Metadata extracted from document (author, date, pages, etc.)"),
    )

    # Vector metadata - stored with each chunk in pgvector for filtering
    vector_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=_(
            "Searchable metadata for pgvector filtering (e.g., {'user_id': '123', 'category': 'research', 'date': '2025-01'})"
        ),
    )

    page_count = models.IntegerField(
        null=True, blank=True, help_text=_("Number of pages (for PDFs, documents)")
    )

    word_count = models.IntegerField(
        null=True, blank=True, help_text=_("Approximate word count")
    )

    # Visibility and access
    is_active = models.BooleanField(
        default=True, help_text=_("Whether this document is active and searchable")
    )

    is_shared = models.BooleanField(
        default=False, help_text=_("Whether document is shared with other users")
    )

    share_settings = models.JSONField(
        default=dict, blank=True, help_text=_("Document sharing configuration")
    )

    # Error tracking
    processing_error = models.TextField(
        blank=True, null=True, help_text=_("Error message if processing failed")
    )

    retry_count = models.IntegerField(
        default=0, help_text=_("Number of processing retries")
    )

    class Meta:
        verbose_name = _("User Document")
        verbose_name_plural = _("User Documents")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="userdoc_user_date_idx"),
            models.Index(fields=["user", "is_active"], name="userdoc_user_active_idx"),
            models.Index(fields=["processing_status"], name="userdoc_status_idx"),
            models.Index(fields=["file_type"], name="userdoc_type_idx"),
            models.Index(
                fields=["vector_collection_name"], name="userdoc_collection_idx"
            ),
            models.Index(
                fields=["user", "vector_collection_name"],
                name="userdoc_user_collection_idx",
            ),
        ]

    def __str__(self):
        return f"{self.file_name} ({self.user.email})"

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def file_size_mb(self):
        """Get file size in MB."""
        if self.file_size:
            return round(self.file_size / (1024 * 1024), 2)
        return 0

    @property
    def file_size_display(self):
        """
        Human-readable file size string.

        Returns '2.5 MB', '340 KB', etc. — ready for templates/serializers.
        """
        size = self.file_size or 0
        if size >= 1024 * 1024:
            return f"{round(size / (1024 * 1024), 1)} MB"
        elif size >= 1024:
            return f"{round(size / 1024, 1)} KB"
        return f"{size} bytes"

    @property
    def is_processable(self):
        """Check if document can be processed for RAG."""
        processable_types = [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
            "text/plain",
            "text/markdown",
            "text/csv",
        ]
        return self.file_type in processable_types

    @property
    def has_embeddings(self):
        """Check if document has been processed and has embeddings."""
        return bool(
            self.processing_status == self.STATUS_COMPLETED
            and self.vector_collection_name
            and self.vector_store_ids
        )

    @property
    def is_pending(self):
        return self.processing_status == self.STATUS_PENDING

    @property
    def is_processing(self):
        return self.processing_status == self.STATUS_PROCESSING

    @property
    def is_completed(self):
        return self.processing_status == self.STATUS_COMPLETED

    @property
    def is_failed(self):
        return self.processing_status == self.STATUS_FAILED

    # ------------------------------------------------------------------
    # Instance methods — processing state machine
    # ------------------------------------------------------------------

    def save(self, *args, **kwargs):
        """Extract file metadata on save."""
        if self.file:
            if not self.file_name:
                self.file_name = os.path.basename(self.file.name)

            if not self.file_extension:
                self.file_extension = os.path.splitext(self.file_name)[1].lower()

            if hasattr(self.file, "size"):
                self.file_size = self.file.size

        super().save(*args, **kwargs)

    def mark_processing_started(self):
        """Mark document as processing."""
        self.processing_status = self.STATUS_PROCESSING
        self.save(update_fields=["processing_status"])

    def mark_processing_completed(
        self,
        collection_name,
        vector_ids,
        chunk_count,
        collection_metadata=None,
        vector_metadata=None,
    ):
        """
        Mark document processing as completed.

        Args:
            collection_name: PGVector collection name (REQUIRED)
            vector_ids: List of document IDs in pgvector
            chunk_count: Number of chunks created
            collection_metadata: Optional metadata for the collection
            vector_metadata: Metadata to be stored with each chunk for filtering
        """
        from django.utils import timezone

        self.processing_status = self.STATUS_COMPLETED
        self.processed_at = timezone.now()
        self.vector_collection_name = collection_name
        self.vector_store_ids = vector_ids
        self.chunk_count = chunk_count

        if collection_metadata:
            self.vector_collection_metadata = collection_metadata

        if vector_metadata:
            self.vector_metadata = vector_metadata

        self.save(
            update_fields=[
                "processing_status",
                "processed_at",
                "vector_collection_name",
                "vector_store_ids",
                "chunk_count",
                "vector_collection_metadata",
                "vector_metadata",
            ]
        )

    def mark_processing_failed(self, error_message):
        """
        Mark document processing as failed.

        Increments retry_count automatically.
        """
        self.processing_status = self.STATUS_FAILED
        self.processing_error = error_message
        self.retry_count += 1

        self.save(
            update_fields=["processing_status", "processing_error", "retry_count"]
        )

    def can_retry_processing(self):
        """Check if the document can be retried (hasn't exceeded MAX_RETRIES)."""
        return self.retry_count < self.MAX_RETRIES and self.processing_status in [
            self.STATUS_FAILED,
            self.STATUS_PENDING,
        ]

    def retry_processing(self):
        """
        Reset status to pending for a retry.

        Returns:
            bool: True if retry was initiated, False if max retries exceeded
        """
        if not self.can_retry_processing():
            return False

        self.processing_status = self.STATUS_PENDING
        self.processing_error = None
        self.save(update_fields=["processing_status", "processing_error"])
        return True

    def deactivate(self):
        """Soft-delete: mark document inactive (hide from search, keep data)."""
        self.is_active = False
        self.save(update_fields=["is_active"])

    def reactivate(self):
        """Reactivate a deactivated document."""
        self.is_active = True
        self.save(update_fields=["is_active"])

    def get_vector_metadata(self):
        """
        Get metadata dict to be stored with vector embeddings.

        Returns:
            dict: Metadata for pgvector filtering
        """
        metadata = {
            "user_id": str(self.user.id),
            "document_id": str(self.id),
            "file_name": self.file_name,
            "file_type": self.file_type,
            "upload_date": self.created_at.isoformat(),
        }

        if self.tags:
            metadata["tags"] = self.tags

        if self.chat_session:
            metadata["session_id"] = str(self.chat_session.id)

        if self.vector_metadata:
            metadata.update(self.vector_metadata)

        return metadata

    def to_display_dict(self):
        """
        Return a serializable dict for API responses.
        """
        return {
            "id": str(self.id),
            "file_name": self.file_name,
            "file_size": self.file_size,
            "file_size_display": self.file_size_display,
            "file_type": self.file_type,
            "processing_status": self.processing_status,
            "has_embeddings": self.has_embeddings,
            "chunk_count": self.chunk_count,
            "page_count": self.page_count,
            "word_count": self.word_count,
            "is_active": self.is_active,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
        }

    # ------------------------------------------------------------------
    # Class methods — queryset helpers
    # ------------------------------------------------------------------

    @classmethod
    def get_user_storage_usage(cls, user):
        """Get total storage used by user's documents."""
        usage = cls.objects.filter(user=user, is_active=True).aggregate(
            total_size=models.Sum("file_size"),
            total_documents=models.Count("id"),
            total_chunks=models.Sum("chunk_count"),
        )

        return {
            "total_size_bytes": usage["total_size"] or 0,
            "total_size_mb": round((usage["total_size"] or 0) / (1024 * 1024), 2),
            "total_documents": usage["total_documents"] or 0,
            "total_chunks": usage["total_chunks"] or 0,
        }

    @classmethod
    def get_documents_in_collection(cls, collection_name, user=None):
        """
        Get all documents in a specific PGVector collection.

        Args:
            collection_name: Name of the pgvector collection
            user: Optional user filter

        Returns:
            QuerySet: Documents in the collection
        """
        queryset = cls.objects.filter(
            vector_collection_name=collection_name,
            processing_status=cls.STATUS_COMPLETED,
        )

        if user:
            queryset = queryset.filter(user=user)

        return queryset

    @classmethod
    def get_user_documents(cls, user, active_only=True):
        """
        Get all documents for a user.

        Args:
            user: User instance
            active_only: Only return active documents

        Returns:
            QuerySet
        """
        qs = cls.objects.filter(user=user)
        if active_only:
            qs = qs.filter(is_active=True)
        return qs.order_by("-created_at")

    @classmethod
    def get_processing_stats(cls, user=None):
        """
        Get document processing statistics.

        Args:
            user: Optional user filter (None = platform-wide)

        Returns:
            dict with counts per status
        """
        qs = cls.objects.all()
        if user:
            qs = qs.filter(user=user)

        from django.db.models import Count, Q

        stats = qs.aggregate(
            total=Count("id"),
            pending=Count("id", filter=Q(processing_status=cls.STATUS_PENDING)),
            processing=Count("id", filter=Q(processing_status=cls.STATUS_PROCESSING)),
            completed=Count("id", filter=Q(processing_status=cls.STATUS_COMPLETED)),
            failed=Count("id", filter=Q(processing_status=cls.STATUS_FAILED)),
        )

        return stats

    @classmethod
    def get_failed_for_retry(cls, user=None):
        """
        Get failed documents eligible for retry.

        Args:
            user: Optional user filter

        Returns:
            QuerySet of failed documents with retry_count < MAX_RETRIES
        """
        qs = cls.objects.filter(
            processing_status=cls.STATUS_FAILED,
            retry_count__lt=cls.MAX_RETRIES,
        )
        if user:
            qs = qs.filter(user=user)
        return qs

    @classmethod
    def create_from_upload(cls, user, uploaded_file, chat_session=None, title=None, tags=None):
        """
        Create a UserDocument from an uploaded file.

        Handles the common pattern of extracting metadata from the
        Django UploadedFile object.

        Args:
            user: User uploading the file
            uploaded_file: Django UploadedFile instance
            chat_session: Optional ChatSession to associate
            title: Optional title (defaults to filename)
            tags: Optional list of tag strings

        Returns:
            UserDocument instance (in 'pending' status)
        """
        doc = cls(
            user=user,
            chat_session=chat_session,
            file=uploaded_file,
            file_name=uploaded_file.name,
            file_size=uploaded_file.size,
            file_type=getattr(uploaded_file, "content_type", "application/octet-stream"),
            file_extension=os.path.splitext(uploaded_file.name)[1].lower(),
            title=title or os.path.splitext(uploaded_file.name)[0],
            tags=tags or [],
        )
        doc.save()
        return doc
