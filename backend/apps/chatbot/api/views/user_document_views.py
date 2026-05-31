# chatbot/api/views/user_document_views.py

"""
Action-based ViewSet for UserDocument model.

Handles file uploads for RAG, processing status tracking, and
document management.

Custom actions (auto-routed by DefaultRouter):
    ┌────────┬────────────────────────────────────────────────┬──────────────┐
    │ Method │ URL                                            │ Action       │
    ├────────┼────────────────────────────────────────────────┼──────────────┤
    │ GET    │ /documents/                                    │ list         │
    │ POST   │ /documents/                                    │ create       │
    │ GET    │ /documents/{id}/                               │ retrieve     │
    │ PATCH  │ /documents/{id}/                               │ partial_update│
    │ DELETE │ /documents/{id}/                               │ destroy      │
    │ POST   │ /documents/{id}/process/                       │ process      │
    │ POST   │ /documents/{id}/retry/                         │ retry        │
    │ GET    │ /documents/{id}/status/                        │ status       │
    │ GET    │ /documents/storage-stats/                      │ storage_stats│
    │ GET    │ /documents/processing-stats/                   │ processing_stats│
    └────────┴────────────────────────────────────────────────┴──────────────┘
"""

from rest_framework import viewsets, status, parsers
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

from drf_spectacular.utils import extend_schema, extend_schema_view

from core.permissions import IsOwnerOrAdmin

from ...models import UserDocument
from ...services import DocumentProcessingService

from ..serializers import (
    UserDocumentSerializer,
    UserDocumentListSerializer,
    UserDocumentCreateSerializer,
    UserDocumentUpdateSerializer,
)


@extend_schema_view(
    list=extend_schema(
        tags=["Documents"], summary="List documents",
        description="List the authenticated user's uploaded documents.",
    ),
    retrieve=extend_schema(
        tags=["Documents"], summary="Retrieve document",
    ),
    create=extend_schema(
        tags=["Documents"], summary="Upload document",
        description="Upload a file for RAG processing (PDF, DOCX, TXT, MD, CSV).",
    ),
    partial_update=extend_schema(
        tags=["Documents"], summary="Update document metadata",
    ),
    destroy=extend_schema(
        tags=["Documents"], summary="Delete document",
        description="Permanently delete a document and its embeddings.",
    ),
)
@extend_schema(tags=["Documents"])
class UserDocumentViewSet(viewsets.ModelViewSet):
    """
    CRUD + processing actions for UserDocument.

    File uploads use multipart form data.  Document processing
    (text extraction, chunking, embedding) is triggered via the
    ``process`` action.
    """

    queryset = UserDocument.objects.all()
    serializer_class = UserDocumentSerializer
    permission_classes = [IsOwnerOrAdmin]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["processing_status", "file_type", "is_active"]
    search_fields = ["file_name", "title", "description"]
    ordering_fields = ["created_at", "file_size", "processing_status"]
    ordering = ["-created_at"]

    # ---- Serializer dispatch ----

    def get_serializer_class(self):
        mapping = {
            "list": UserDocumentListSerializer,
            "create": UserDocumentCreateSerializer,
            "update": UserDocumentUpdateSerializer,
            "partial_update": UserDocumentUpdateSerializer,
        }
        return mapping.get(self.action, UserDocumentSerializer)

    # ---- Queryset ----

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return UserDocument.objects.none()

        qs = UserDocument.objects.select_related("user", "chat_session").all()

        user = self.request.user
        if not (user.is_staff or user.is_superuser or user.role == "admin"):
            qs = qs.filter(user=user)

        return qs

    # ---- Lifecycle hooks ----

    def perform_create(self, serializer):
        """Create document record from upload via model helper."""
        doc = UserDocument.create_from_upload(
            user=self.request.user,
            uploaded_file=serializer.validated_data["file"],
            chat_session=serializer.validated_data.get("chat_session"),
            title=serializer.validated_data.get("title"),
            tags=serializer.validated_data.get("tags", []),
        )
        serializer.instance = doc

    def perform_destroy(self, instance):
        """Delete document including embeddings and file."""
        DocumentProcessingService.delete_document(
            document_id=instance.id,
            user_id=instance.user.id,
            delete_file=True,
        )

    # ---- Custom actions ----

    @extend_schema(
        summary="Process document",
        description="Trigger document processing (text extraction, chunking, embedding).",
        responses={200: dict},
    )
    @action(detail=True, methods=["post"], url_path="process")
    def process(self, request, pk=None):
        """POST /documents/{id}/process/"""
        doc = self.get_object()

        if doc.processing_status == UserDocument.STATUS_PROCESSING:
            return Response(
                {"message": "Document is already being processed."},
                status=status.HTTP_409_CONFLICT,
            )

        if doc.processing_status == UserDocument.STATUS_COMPLETED:
            return Response(
                {"message": "Document is already processed. Use retry to reprocess."},
                status=status.HTTP_409_CONFLICT,
            )

        # TODO: Trigger Celery task for async processing
        # process_document_task.delay(doc.id, request.user.id)

        # For now, mark as started
        doc.mark_processing_started()
        return Response({
            "message": "Document processing started.",
            "document_id": str(doc.id),
            "status": "processing",
        })

    @extend_schema(
        summary="Retry processing",
        description="Retry failed document processing.",
        responses={200: dict},
    )
    @action(detail=True, methods=["post"], url_path="retry")
    def retry(self, request, pk=None):
        """POST /documents/{id}/retry/"""
        doc = self.get_object()

        if not doc.can_retry_processing():
            return Response(
                {
                    "message": "Cannot retry: max retries exceeded or document not in a retryable state.",
                    "retry_count": doc.retry_count,
                    "max_retries": UserDocument.MAX_RETRIES,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        success = doc.retry_processing()
        if success:
            # TODO: Trigger Celery task
            return Response({
                "message": "Retry initiated.",
                "document_id": str(doc.id),
                "status": "pending",
            })

        return Response(
            {"message": "Retry failed."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @extend_schema(
        summary="Processing status",
        description="Get detailed processing status for a document.",
        responses={200: dict},
    )
    @action(detail=True, methods=["get"], url_path="status")
    def status(self, request, pk=None):
        """GET /documents/{id}/status/"""
        doc = self.get_object()
        result = DocumentProcessingService.get_processing_status(doc.id)
        return Response(result)

    @extend_schema(
        summary="Storage statistics",
        description="Get storage usage for the authenticated user.",
        responses={200: dict},
    )
    @action(detail=False, methods=["get"], url_path="storage-stats")
    def storage_stats(self, request):
        """GET /documents/storage-stats/"""
        stats = UserDocument.get_user_storage_usage(request.user)
        return Response(stats)

    @extend_schema(
        summary="Processing statistics",
        description="Get document processing statistics.",
        responses={200: dict},
    )
    @action(detail=False, methods=["get"], url_path="processing-stats")
    def processing_stats(self, request):
        """GET /documents/processing-stats/"""
        stats = UserDocument.get_processing_stats(user=request.user)
        return Response(stats)
