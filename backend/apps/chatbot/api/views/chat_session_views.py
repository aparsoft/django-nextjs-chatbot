# chatbot/api/views/chat_session_views.py

"""
Action-based ViewSet for ChatSession model.

CRUD + custom actions for managing conversation threads.

Custom actions (auto-routed by DefaultRouter):
    ┌────────┬────────────────────────────────────────────────┬──────────────┐
    │ Method │ URL                                            │ Action       │
    ├────────┼────────────────────────────────────────────────┼──────────────┤
    │ GET    │ /chat-sessions/                               │ list         │
    │ POST   │ /chat-sessions/                               │ create       │
    │ GET    │ /chat-sessions/{id}/                          │ retrieve     │
    │ PATCH  │ /chat-sessions/{id}/                          │ partial_update│
    │ DELETE │ /chat-sessions/{id}/                          │ destroy      │
    │ GET    │ /chat-sessions/archived/                      │ archived     │
    │ GET    │ /chat-sessions/pinned/                        │ pinned       │
    │ GET    │ /chat-sessions/stats/                         │ stats        │
    │ POST   │ /chat-sessions/{id}/archive/                  │ archive      │
    │ POST   │ /chat-sessions/{id}/activate/                 │ activate     │
    │ POST   │ /chat-sessions/{id}/pin/                      │ pin          │
    │ GET    │ /chat-sessions/{id}/analytics/                │ analytics    │
    └────────┴────────────────────────────────────────────────┴──────────────┘

Business logic lives in ChatSessionService — the viewset only handles
HTTP concerns (request parsing, response formatting, status codes).
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

from drf_spectacular.utils import extend_schema, extend_schema_view

from core.permissions import IsOwnerOrAdmin

from ...models import ChatSession
from ...services import ChatSessionService

from ..serializers import (
    ChatSessionSerializer,
    ChatSessionListSerializer,
    ChatSessionCreateSerializer,
    ChatSessionUpdateSerializer,
)


# ---------------------------------------------------------------------------
#  ChatSession ViewSet
# ---------------------------------------------------------------------------


@extend_schema_view(
    list=extend_schema(
        tags=["Chat Sessions"],
        summary="List chat sessions",
        description="Return the authenticated user's chat sessions.",
    ),
    retrieve=extend_schema(
        tags=["Chat Sessions"],
        summary="Retrieve chat session",
        description="Get full details for a single chat session.",
    ),
    create=extend_schema(
        tags=["Chat Sessions"],
        summary="Create chat session",
        description="Start a new conversation. Defaults come from user preferences.",
    ),
    partial_update=extend_schema(
        tags=["Chat Sessions"],
        summary="Update chat session",
        description="Update session title, settings, or status.",
    ),
    destroy=extend_schema(
        tags=["Chat Sessions"],
        summary="Delete chat session",
        description="Soft-delete the session (archive + deactivate).",
    ),
)
@extend_schema(tags=["Chat Sessions"])
class ChatSessionViewSet(viewsets.ModelViewSet):
    """
    CRUD + custom actions for ChatSession.

    Regular users see only their own sessions; admins see all.
    The queryset is scoped in ``get_queryset()`` as the first layer
    of defence; ``IsOwnerOrAdmin`` adds object-level checks.
    """

    queryset = ChatSession.objects.all()
    serializer_class = ChatSessionSerializer
    permission_classes = [IsOwnerOrAdmin]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["is_active", "is_archived", "is_pinned", "model_name"]
    search_fields = ["title", "description"]
    ordering_fields = [
        "created_at",
        "updated_at",
        "last_message_at",
        "message_count",
        "title",
    ]
    ordering = ["-is_pinned", "-last_message_at"]

    # ---- Serializer dispatch ----

    def get_serializer_class(self):
        """Return the appropriate serializer for the current action."""
        mapping = {
            "list": ChatSessionListSerializer,
            "create": ChatSessionCreateSerializer,
            "update": ChatSessionUpdateSerializer,
            "partial_update": ChatSessionUpdateSerializer,
        }
        return mapping.get(self.action, ChatSessionSerializer)

    # ---- Queryset ----

    def get_queryset(self):
        """Scope to owner; eager-load relations; guard schema introspection."""
        if getattr(self, "swagger_fake_view", False):
            return ChatSession.objects.none()

        qs = ChatSession.objects.select_related("user").all()

        user = self.request.user
        if not (user.is_staff or user.is_superuser or user.role == "admin"):
            qs = qs.filter(user=user)

        # The default list/retrieve actions exclude soft-deleted sessions
        # (is_active=False AND is_archived=True). The `archived` and `pinned`
        # custom actions use their own model methods, so they bypass this.
        if self.action in ("list", "retrieve", "update", "partial_update"):
            qs = qs.filter(is_active=True, is_archived=False)

        return qs

    # ---- Lifecycle hooks (delegate to service) ----

    def perform_create(self, serializer):
        """
        Create session via ChatSessionService to pull defaults from
        user preferences automatically.
        """
        session = ChatSessionService.create_session(
            user=self.request.user,
            **serializer.validated_data,
        )
        # Re-serialize the created instance for the response
        serializer.instance = session

    def perform_destroy(self, instance):
        """Soft-delete instead of hard-delete."""
        instance.soft_delete()

    # ---- Custom actions ----

    @extend_schema(
        summary="List archived sessions",
        description="Return archived sessions for the authenticated user.",
        responses={200: ChatSessionListSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="archived")
    def archived(self, request):
        """GET /chat-sessions/archived/"""
        sessions = ChatSession.get_archived_for_user(request.user)
        page = self.paginate_queryset(sessions)
        if page is not None:
            serializer = ChatSessionListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = ChatSessionListSerializer(sessions, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="List pinned sessions",
        description="Return pinned sessions for the authenticated user.",
        responses={200: ChatSessionListSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="pinned")
    def pinned(self, request):
        """GET /chat-sessions/pinned/"""
        sessions = ChatSession.get_pinned_for_user(request.user)
        serializer = ChatSessionListSerializer(sessions, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Session statistics",
        description="Aggregate session statistics for the authenticated user.",
        responses={200: dict},
    )
    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        """GET /chat-sessions/stats/ — aggregate session stats."""
        stats = ChatSession.get_session_stats(request.user)
        return Response(stats)

    @extend_schema(
        summary="Archive session",
        description="Archive a chat session (sets inactive + archived).",
        responses={200: ChatSessionSerializer},
    )
    @action(detail=True, methods=["post"], url_path="archive")
    def archive(self, request, pk=None):
        """POST /chat-sessions/{id}/archive/"""
        session = self.get_object()
        session.archive()
        serializer = ChatSessionSerializer(session)
        return Response(serializer.data)

    @extend_schema(
        summary="Activate session",
        description="Reactivate an archived chat session.",
        responses={200: ChatSessionSerializer},
    )
    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        """POST /chat-sessions/{id}/activate/"""
        session = self.get_object()
        session.activate()
        serializer = ChatSessionSerializer(session)
        return Response(serializer.data)

    @extend_schema(
        summary="Toggle pin",
        description="Toggle the pin status of a chat session.",
        responses={200: ChatSessionSerializer},
    )
    @action(detail=True, methods=["post"], url_path="pin")
    def pin(self, request, pk=None):
        """POST /chat-sessions/{id}/pin/"""
        session = self.get_object()
        session.toggle_pin()
        serializer = ChatSessionSerializer(session)
        return Response(serializer.data)

    @extend_schema(
        summary="Session analytics",
        description="Get detailed analytics for a specific chat session.",
        responses={200: dict},
    )
    @action(detail=True, methods=["get"], url_path="analytics")
    def analytics(self, request, pk=None):
        """GET /chat-sessions/{id}/analytics/"""
        session = self.get_object()
        stats = ChatSessionService.get_session_statistics(
            session_id=session.id,
            user=request.user,
        )
        return Response(stats)
