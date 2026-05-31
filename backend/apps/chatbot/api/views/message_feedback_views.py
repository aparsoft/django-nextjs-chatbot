# chatbot/api/views/message_feedback_views.py

"""
Action-based ViewSet for MessageFeedback model.

Users rate AI responses and report issues.  Admin review is handled
through the ``review`` action.

Custom actions (auto-routed by DefaultRouter):
    ┌────────┬────────────────────────────────────────────────┬──────────────┐
    │ Method │ URL                                            │ Action       │
    ├────────┼────────────────────────────────────────────────┼──────────────┤
    │ GET    │ /message-feedback/                             │ list         │
    │ POST   │ /message-feedback/                             │ create       │
    │ GET    │ /message-feedback/{id}/                        │ retrieve     │
    │ PATCH  │ /message-feedback/{id}/                        │ partial_update│
    │ DELETE │ /message-feedback/{id}/                        │ destroy      │
    │ POST   │ /message-feedback/{id}/review/                 │ review       │
    │ GET    │ /message-feedback/stats/                       │ stats        │
    └────────┴────────────────────────────────────────────────┴──────────────┘
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

from drf_spectacular.utils import extend_schema, extend_schema_view

from core.permissions import IsOwnerOrAdmin, IsAdminUser

from ...models import MessageFeedback

from ..serializers import (
    MessageFeedbackSerializer,
    MessageFeedbackListSerializer,
    MessageFeedbackCreateSerializer,
    MessageFeedbackUpdateSerializer,
)


@extend_schema_view(
    list=extend_schema(
        tags=["Message Feedback"], summary="List feedback",
        description="List feedback for the authenticated user's messages.",
    ),
    retrieve=extend_schema(
        tags=["Message Feedback"], summary="Retrieve feedback",
    ),
    create=extend_schema(
        tags=["Message Feedback"], summary="Create feedback",
        description="Rate an AI response or report an issue.",
    ),
    partial_update=extend_schema(
        tags=["Message Feedback"], summary="Update feedback",
    ),
    destroy=extend_schema(
        tags=["Message Feedback"], summary="Delete feedback",
    ),
)
@extend_schema(tags=["Message Feedback"])
class MessageFeedbackViewSet(viewsets.ModelViewSet):
    """CRUD + review action for MessageFeedback."""

    queryset = MessageFeedback.objects.all()
    serializer_class = MessageFeedbackSerializer
    permission_classes = [IsOwnerOrAdmin]
    filter_backends = [
        DjangoFilterBackend,
        filters.OrderingFilter,
    ]
    filterset_fields = ["rating", "chat_session", "reviewed"]
    ordering_fields = ["created_at", "rating"]
    ordering = ["-created_at"]

    # ---- Serializer dispatch ----

    def get_serializer_class(self):
        mapping = {
            "list": MessageFeedbackListSerializer,
            "create": MessageFeedbackCreateSerializer,
            "update": MessageFeedbackUpdateSerializer,
            "partial_update": MessageFeedbackUpdateSerializer,
        }
        return mapping.get(self.action, MessageFeedbackSerializer)

    # ---- Queryset ----

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return MessageFeedback.objects.none()

        qs = MessageFeedback.objects.select_related(
            "user", "chat_session"
        ).all()

        user = self.request.user
        if not (user.is_staff or user.is_superuser or user.role == "admin"):
            qs = qs.filter(user=user)

        return qs

    # ---- Lifecycle hooks ----

    def perform_create(self, serializer):
        """Inject user from request."""
        serializer.save(user=self.request.user)

    # ---- Custom actions ----

    @extend_schema(
        summary="Review feedback (admin)",
        description="Admin review of user feedback with optional notes.",
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "admin_notes": {"type": "string"},
                    "action_taken": {"type": "string"},
                },
            }
        },
        responses={200: MessageFeedbackSerializer},
    )
    @action(detail=True, methods=["post"], url_path="review")
    def review(self, request, pk=None):
        """POST /message-feedback/{id}/review/ — admin only."""
        feedback = self.get_object()
        admin_notes = request.data.get("admin_notes", "")
        action_taken = request.data.get("action_taken", "")

        feedback.reviewed = True
        feedback.reviewed_by = request.user
        feedback.admin_notes = admin_notes
        feedback.action_taken = action_taken

        from django.utils import timezone
        feedback.reviewed_at = timezone.now()
        feedback.save()

        serializer = MessageFeedbackSerializer(feedback)
        return Response(serializer.data)

    @extend_schema(
        summary="Feedback statistics",
        description="Aggregate feedback stats for the authenticated user.",
        responses={200: dict},
    )
    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        """GET /message-feedback/stats/"""
        from django.db.models import Count, Q

        qs = MessageFeedback.objects.filter(user=request.user)
        stats = qs.aggregate(
            total_feedback=Count("id"),
            thumbs_up=Count("id", filter=Q(rating="thumbs_up")),
            thumbs_down=Count("id", filter=Q(rating="thumbs_down")),
            reviewed=Count("id", filter=Q(reviewed=True)),
            unreviewed=Count("id", filter=Q(reviewed=False)),
        )
        return Response(stats)
