# chatbot/api/views/token_usage_views.py

"""
ReadOnly ViewSet for TokenUsage model.

TokenUsage records are created programmatically by the AI service
layer (via TokenUsageService.track_usage).  The API only exposes
read endpoints for analytics and dashboards.

Custom actions (auto-routed by DefaultRouter):
    ┌────────┬────────────────────────────────────────────────┬──────────────┐
    │ Method │ URL                                            │ Action       │
    ├────────┼────────────────────────────────────────────────┼──────────────┤
    │ GET    │ /token-usage/                                  │ list         │
    │ GET    │ /token-usage/{id}/                             │ retrieve     │
    │ GET    │ /token-usage/usage-stats/                      │ usage_stats  │
    │ GET    │ /token-usage/daily-usage/                      │ daily_usage  │
    │ GET    │ /token-usage/check-limits/                     │ check_limits │
    │ GET    │ /token-usage/model-breakdown/                  │ model_breakdown│
    └────────┴────────────────────────────────────────────────┴──────────────┘

No create / update / delete — records are immutable once created.
"""

from rest_framework import viewsets, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

from drf_spectacular.utils import extend_schema, extend_schema_view

from core.permissions import IsOwnerOrAdmin

from ...models import TokenUsage
from ...services import TokenUsageService

from ..serializers import (
    TokenUsageSerializer,
    TokenUsageListSerializer,
)


@extend_schema_view(
    list=extend_schema(
        tags=["Token Usage"], summary="List token usage",
        description="Token usage records for the authenticated user.",
    ),
    retrieve=extend_schema(
        tags=["Token Usage"], summary="Retrieve token usage",
    ),
)
@extend_schema(tags=["Token Usage"])
class TokenUsageViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Read-only ViewSet for TokenUsage.

    Records are created by the service layer during AI interactions.
    This ViewSet only provides read + analytics endpoints.
    """

    queryset = TokenUsage.objects.all()
    serializer_class = TokenUsageSerializer
    permission_classes = [IsOwnerOrAdmin]
    filter_backends = [
        DjangoFilterBackend,
        filters.OrderingFilter,
    ]
    filterset_fields = ["model_name", "request_type", "had_error", "was_cached"]
    ordering_fields = ["created_at", "total_tokens", "total_cost", "response_time_ms"]
    ordering = ["-created_at"]

    # ---- Serializer dispatch ----

    def get_serializer_class(self):
        if self.action == "list":
            return TokenUsageListSerializer
        return TokenUsageSerializer

    # ---- Queryset ----

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return TokenUsage.objects.none()

        qs = TokenUsage.objects.select_related("user", "chat_session").all()

        user = self.request.user
        if not (user.is_staff or user.is_superuser or user.role == "admin"):
            qs = qs.filter(user=user)

        return qs

    # ---- Custom actions ----

    @extend_schema(
        summary="Usage statistics",
        description="Aggregate token usage stats for the authenticated user over the last N days.",
        responses={200: dict},
    )
    @action(detail=False, methods=["get"], url_path="usage-stats")
    def usage_stats(self, request):
        """GET /token-usage/usage-stats/?days=30"""
        days = int(request.query_params.get("days", 30))
        stats = TokenUsageService.get_user_usage_stats(
            user=request.user, days=days
        )
        return Response(stats)

    @extend_schema(
        summary="Daily usage",
        description="Get token usage for a specific date (defaults to today).",
        responses={200: dict},
    )
    @action(detail=False, methods=["get"], url_path="daily-usage")
    def daily_usage(self, request):
        """GET /token-usage/daily-usage/"""
        from datetime import datetime

        date_str = request.query_params.get("date")
        date = None
        if date_str:
            date = datetime.strptime(date_str, "%Y-%m-%d")

        usage = TokenUsageService.get_daily_usage(
            user=request.user, date=date
        )
        return Response(usage)

    @extend_schema(
        summary="Check usage limits",
        description="Check if the user has exceeded daily usage limits.",
        responses={200: dict},
    )
    @action(detail=False, methods=["get"], url_path="check-limits")
    def check_limits(self, request):
        """GET /token-usage/check-limits/?additional_tokens=500"""
        additional = int(request.query_params.get("additional_tokens", 0))
        result = TokenUsageService.check_user_limits(
            user=request.user, additional_tokens=additional
        )
        return Response(result)

    @extend_schema(
        summary="Model breakdown",
        description="Token usage breakdown by AI model.",
        responses={200: dict},
    )
    @action(detail=False, methods=["get"], url_path="model-breakdown")
    def model_breakdown(self, request):
        """GET /token-usage/model-breakdown/"""
        breakdown = TokenUsage.get_model_breakdown(request.user)
        # Convert Decimal values for JSON
        data = [
            {
                "model_name": entry["model_name"],
                "total_tokens": entry["total_tokens"],
                "total_cost": float(entry["total_cost"]),
                "request_count": entry["request_count"],
            }
            for entry in breakdown
        ]
        return Response(data)
