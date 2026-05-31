# chatbot/api/views/user_api_key_views.py

"""
Action-based ViewSet for UserAPIKey model.

Encrypted API keys — the raw key is NEVER exposed in responses.
Only the masked display_key is returned.

Custom actions (auto-routed by DefaultRouter):
    ┌────────┬────────────────────────────────────────────────┬──────────────┐
    │ Method │ URL                                            │ Action       │
    ├────────┼────────────────────────────────────────────────┼──────────────┤
    │ GET    │ /api-keys/                                     │ list         │
    │ POST   │ /api-keys/                                     │ create       │
    │ GET    │ /api-keys/{id}/                                │ retrieve     │
    │ PATCH  │ /api-keys/{id}/                                │ partial_update│
    │ DELETE │ /api-keys/{id}/                                │ destroy      │
    │ POST   │ /api-keys/{id}/validate/                       │ validate     │
    │ POST   │ /api-keys/{id}/set-default/                    │ set_default  │
    │ POST   │ /api-keys/{id}/deactivate/                     │ deactivate   │
    │ GET    │ /api-keys/providers/                           │ providers    │
    │ GET    │ /api-keys/usage-summary/                       │ usage_summary│
    └────────┴────────────────────────────────────────────────┴──────────────┘
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

from drf_spectacular.utils import extend_schema, extend_schema_view

from core.permissions import IsOwnerOrAdmin

from ...models import UserAPIKey
from ...services import APIKeyService

from ..serializers import (
    UserAPIKeySerializer,
    UserAPIKeyListSerializer,
    UserAPIKeyCreateSerializer,
    UserAPIKeyUpdateSerializer,
)


@extend_schema_view(
    list=extend_schema(
        tags=["API Keys"], summary="List API keys",
        description="List the authenticated user's API keys (masked).",
    ),
    retrieve=extend_schema(
        tags=["API Keys"], summary="Retrieve API key",
    ),
    create=extend_schema(
        tags=["API Keys"], summary="Add API key",
        description="Store a new API key (encrypted).",
    ),
    partial_update=extend_schema(
        tags=["API Keys"], summary="Update API key",
    ),
    destroy=extend_schema(
        tags=["API Keys"], summary="Delete API key",
    ),
)
@extend_schema(tags=["API Keys"])
class UserAPIKeyViewSet(viewsets.ModelViewSet):
    """CRUD + management actions for UserAPIKey."""

    queryset = UserAPIKey.objects.all()
    serializer_class = UserAPIKeySerializer
    permission_classes = [IsOwnerOrAdmin]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["provider", "is_active", "is_default", "is_validated"]
    search_fields = ["key_name", "provider"]
    ordering_fields = ["-is_default", "-last_used_at", "created_at"]
    ordering = ["-is_default", "-last_used_at"]

    # ---- Serializer dispatch ----

    def get_serializer_class(self):
        mapping = {
            "list": UserAPIKeyListSerializer,
            "create": UserAPIKeyCreateSerializer,
            "update": UserAPIKeyUpdateSerializer,
            "partial_update": UserAPIKeyUpdateSerializer,
        }
        return mapping.get(self.action, UserAPIKeySerializer)

    # ---- Queryset ----

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return UserAPIKey.objects.none()

        qs = UserAPIKey.objects.select_related("user").all()

        user = self.request.user
        if not (user.is_staff or user.is_superuser or user.role == "admin"):
            qs = qs.filter(user=user)

        return qs

    # ---- Custom actions ----

    @extend_schema(
        summary="Validate API key",
        description="Validate the API key with the provider.",
        responses={200: dict},
    )
    @action(detail=True, methods=["post"], url_path="validate")
    def validate(self, request, pk=None):
        """POST /api-keys/{id}/validate/"""
        api_key = self.get_object()
        result = api_key.validate_key()
        return Response(result)

    @extend_schema(
        summary="Set as default",
        description="Set this key as the default for its provider.",
        responses={200: UserAPIKeySerializer},
    )
    @action(detail=True, methods=["post"], url_path="set-default")
    def set_default(self, request, pk=None):
        """POST /api-keys/{id}/set-default/"""
        updated = APIKeyService.set_default_key(
            user=request.user, key_id=pk
        )
        serializer = UserAPIKeySerializer(updated)
        return Response(serializer.data)

    @extend_schema(
        summary="Deactivate API key",
        description="Soft-delete: deactivate the key (can be reactivated later).",
        responses={200: UserAPIKeySerializer},
    )
    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        """POST /api-keys/{id}/deactivate/"""
        api_key = self.get_object()
        api_key.deactivate()
        serializer = UserAPIKeySerializer(api_key)
        return Response(serializer.data)

    @extend_schema(
        summary="List providers",
        description="Get the list of providers the user has active keys for.",
        responses={200: dict},
    )
    @action(detail=False, methods=["get"], url_path="providers")
    def providers(self, request):
        """GET /api-keys/providers/"""
        providers = UserAPIKey.get_providers_for_user(request.user)
        return Response({"providers": providers})

    @extend_schema(
        summary="Usage summary",
        description="Aggregated usage stats across all API keys.",
        responses={200: dict},
    )
    @action(detail=False, methods=["get"], url_path="usage-summary")
    def usage_summary(self, request):
        """GET /api-keys/usage-summary/"""
        summary = UserAPIKey.get_usage_summary(request.user)
        return Response(summary)
