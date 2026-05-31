# chatbot/api/views/user_preference_views.py

"""
Action-based ViewSet for UserPreference model.

One-to-one with user — most users have exactly one preference record.

Custom actions (auto-routed by DefaultRouter):
    ┌────────┬────────────────────────────────────────────────┬──────────────┐
    │ Method │ URL                                            │ Action       │
    ├────────┼────────────────────────────────────────────────┼──────────────┤
    │ GET    │ /preferences/me/                               │ me           │
    │ GET    │ /preferences/session-config/                   │ session_config│
    │ POST   │ /preferences/reset-defaults/                   │ reset_defaults│
    └────────┴────────────────────────────────────────────────┴──────────────┘

Because UserPreference has a OneToOneField to User, the list/retrieve
endpoints are less useful than ``me`` for regular users.  The ViewSet
still provides full CRUD for admin access.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from drf_spectacular.utils import extend_schema, extend_schema_view

from core.permissions import IsOwnerOrAdmin

from ...models import UserPreference
from ...services import UserPreferenceService

from ..serializers import (
    UserPreferenceSerializer,
    UserPreferenceListSerializer,
    UserPreferenceCreateSerializer,
    UserPreferenceUpdateSerializer,
)


@extend_schema_view(
    list=extend_schema(
        tags=["User Preferences"], summary="List preferences",
        description="Admin: list all user preferences. Regular users see only their own.",
    ),
    retrieve=extend_schema(
        tags=["User Preferences"], summary="Retrieve preference",
    ),
    create=extend_schema(
        tags=["User Preferences"], summary="Create preference",
        description="Create preferences for a user (usually auto-created on registration).",
    ),
    partial_update=extend_schema(
        tags=["User Preferences"], summary="Update preference",
        description="Update preference fields (partial).",
    ),
    destroy=extend_schema(
        tags=["User Preferences"], summary="Delete preference",
    ),
)
@extend_schema(tags=["User Preferences"])
class UserPreferenceViewSet(viewsets.ModelViewSet):
    """
    CRUD + custom actions for UserPreference.

    Regular users interact via the ``me`` action; full CRUD is
    available for admin management.
    """

    queryset = UserPreference.objects.all()
    serializer_class = UserPreferenceSerializer
    permission_classes = [IsOwnerOrAdmin]
    http_method_names = ["get", "post", "patch", "delete"]  # no PUT

    # ---- Serializer dispatch ----

    def get_serializer_class(self):
        mapping = {
            "list": UserPreferenceListSerializer,
            "create": UserPreferenceCreateSerializer,
            "update": UserPreferenceUpdateSerializer,
            "partial_update": UserPreferenceUpdateSerializer,
        }
        return mapping.get(self.action, UserPreferenceSerializer)

    # ---- Queryset ----

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return UserPreference.objects.none()

        qs = UserPreference.objects.select_related("user").all()

        user = self.request.user
        if not (user.is_staff or user.is_superuser or user.role == "admin"):
            qs = qs.filter(user=user)

        return qs

    # ---- Lifecycle hooks ----

    def perform_create(self, serializer):
        """Inject user from request if not provided."""
        serializer.save(user=self.request.user)

    # ---- Custom actions ----

    @extend_schema(
        summary="Get my preferences",
        description="Return the authenticated user's preferences (auto-created if missing).",
        responses={200: UserPreferenceSerializer},
    )
    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        """GET /preferences/me/"""
        prefs = UserPreferenceService.get_or_create_preferences(request.user)
        serializer = UserPreferenceSerializer(prefs)
        return Response(serializer.data)

    @extend_schema(
        summary="Get session config",
        description="Return the config dict used to create new chat sessions.",
        responses={200: dict},
    )
    @action(detail=False, methods=["get"], url_path="session-config")
    def session_config(self, request):
        """GET /preferences/session-config/"""
        config = UserPreferenceService.get_session_config(request.user)
        return Response(config)

    @extend_schema(
        summary="Reset to defaults",
        description="Reset all preferences to platform defaults.",
        responses={200: UserPreferenceSerializer},
    )
    @action(detail=False, methods=["post"], url_path="reset-defaults")
    def reset_defaults(self, request):
        """POST /preferences/reset-defaults/"""
        prefs = UserPreferenceService.reset_to_defaults(request.user)
        serializer = UserPreferenceSerializer(prefs)
        return Response(serializer.data)
