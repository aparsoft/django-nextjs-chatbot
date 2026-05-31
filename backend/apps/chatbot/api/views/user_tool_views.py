# chatbot/api/views/user_tool_views.py

"""
Action-based ViewSet for UserTool model.

Tools are defined in code (TOOL_REGISTRY) and users enable/disable
them with per-user configuration.

Custom actions (auto-routed by DefaultRouter):
    ┌────────┬────────────────────────────────────────────────┬──────────────┐
    │ Method │ URL                                            │ Action       │
    ├────────┼────────────────────────────────────────────────┼──────────────┤
    │ GET    │ /tools/                                        │ list         │
    │ POST   │ /tools/                                        │ create       │
    │ GET    │ /tools/{id}/                                   │ retrieve     │
    │ PATCH  │ /tools/{id}/                                   │ partial_update│
    │ DELETE │ /tools/{id}/                                   │ destroy      │
    │ POST   │ /tools/{id}/activate/                          │ activate     │
    │ POST   │ /tools/{id}/deactivate/                        │ deactivate   │
    │ GET    │ /tools/{id}/rate-limit-status/                 │ rate_limit_status│
    │ GET    │ /tools/registry/                               │ registry     │
    │ POST   │ /tools/seed/                                   │ seed         │
    │ GET    │ /tools/enabled/                                │ enabled      │
    └────────┴────────────────────────────────────────────────┴──────────────┘
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

from drf_spectacular.utils import extend_schema, extend_schema_view

from core.permissions import IsOwnerOrAdmin

from ...models import UserTool, TOOL_REGISTRY
from ...services import ToolService

from ..serializers import (
    UserToolSerializer,
    UserToolListSerializer,
    UserToolCreateSerializer,
    UserToolUpdateSerializer,
)


@extend_schema_view(
    list=extend_schema(
        tags=["Tools"], summary="List user tools",
        description="List the authenticated user's configured tools.",
    ),
    retrieve=extend_schema(
        tags=["Tools"], summary="Retrieve tool",
    ),
    create=extend_schema(
        tags=["Tools"], summary="Create tool",
        description="Enable a tool from TOOL_REGISTRY for the user.",
    ),
    partial_update=extend_schema(
        tags=["Tools"], summary="Update tool configuration",
    ),
    destroy=extend_schema(
        tags=["Tools"], summary="Delete tool",
    ),
)
@extend_schema(tags=["Tools"])
class UserToolViewSet(viewsets.ModelViewSet):
    """CRUD + tool management actions for UserTool."""

    queryset = UserTool.objects.all()
    serializer_class = UserToolSerializer
    permission_classes = [IsOwnerOrAdmin]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["tool_name", "is_enabled", "category", "is_approved"]
    search_fields = ["tool_name", "tool_display_name", "description"]
    ordering_fields = ["tool_display_name", "usage_count", "last_used_at"]
    ordering = ["tool_display_name"]

    # ---- Serializer dispatch ----

    def get_serializer_class(self):
        mapping = {
            "list": UserToolListSerializer,
            "create": UserToolCreateSerializer,
            "update": UserToolUpdateSerializer,
            "partial_update": UserToolUpdateSerializer,
        }
        return mapping.get(self.action, UserToolSerializer)

    # ---- Queryset ----

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return UserTool.objects.none()

        qs = UserTool.objects.select_related("user", "approved_by").all()

        user = self.request.user
        if not (user.is_staff or user.is_superuser or user.role == "admin"):
            qs = qs.filter(user=user)

        return qs

    # ---- Lifecycle hooks ----

    def perform_create(self, serializer):
        """Delegate to model's enable_tool() for registry integration."""
        tool = UserTool.enable_tool(
            user=self.request.user,
            tool_name=serializer.validated_data["tool_name"],
            configuration=serializer.validated_data.get("configuration"),
        )
        serializer.instance = tool

    # ---- Custom actions ----

    @extend_schema(
        summary="Activate tool",
        description="Enable a tool for the user.",
        responses={200: UserToolSerializer},
    )
    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        """POST /tools/{id}/activate/"""
        tool = self.get_object()
        tool.activate()
        serializer = UserToolSerializer(tool)
        return Response(serializer.data)

    @extend_schema(
        summary="Deactivate tool",
        description="Disable a tool for the user.",
        responses={200: UserToolSerializer},
    )
    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        """POST /tools/{id}/deactivate/"""
        tool = self.get_object()
        tool.deactivate()
        serializer = UserToolSerializer(tool)
        return Response(serializer.data)

    @extend_schema(
        summary="Rate limit status",
        description="Check if the user has exceeded rate limits for this tool.",
        responses={200: dict},
    )
    @action(detail=True, methods=["get"], url_path="rate-limit-status")
    def rate_limit_status(self, request, pk=None):
        """GET /tools/{id}/rate-limit-status/"""
        tool = self.get_object()
        result = tool.check_rate_limit()
        return Response(result)

    @extend_schema(
        summary="Tool registry",
        description="List all available tools from the TOOL_REGISTRY (code-defined).",
        responses={200: dict},
    )
    @action(detail=False, methods=["get"], url_path="registry")
    def registry(self, request):
        """GET /tools/registry/"""
        return Response(TOOL_REGISTRY)

    @extend_schema(
        summary="Seed tools",
        description="Create UserTool entries for every tool in TOOL_REGISTRY for the current user.",
        responses={200: dict},
    )
    @action(detail=False, methods=["post"], url_path="seed")
    def seed(self, request):
        """POST /tools/seed/"""
        seeded = UserTool.seed_all_tools(request.user)
        created_count = sum(1 for _, created in seeded if created)
        return Response({
            "message": f"Seeded {len(seeded)} tools ({created_count} new).",
            "total": len(seeded),
            "created": created_count,
        })

    @extend_schema(
        summary="List enabled tools",
        description="Get the user's enabled + approved tools (ready for agent use).",
        responses={200: UserToolListSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="enabled")
    def enabled(self, request):
        """GET /tools/enabled/"""
        tools = UserTool.get_enabled_for_user(request.user)
        serializer = UserToolListSerializer(tools, many=True)
        return Response(serializer.data)
