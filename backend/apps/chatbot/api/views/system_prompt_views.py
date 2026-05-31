# chatbot/api/views/system_prompt_views.py

"""
Action-based ViewSet for SystemPromptTemplate model.

System prompts are shared resources — any authenticated user can read
public/active templates, but only admins can create/update/delete.

Custom actions (auto-routed by DefaultRouter):
    ┌────────┬────────────────────────────────────────────────┬──────────────┐
    │ Method │ URL                                            │ Action       │
    ├────────┼────────────────────────────────────────────────┼──────────────┤
    │ GET    │ /system-prompts/                               │ list         │
    │ POST   │ /system-prompts/                               │ create       │
    │ GET    │ /system-prompts/{id}/                          │ retrieve     │
    │ PATCH  │ /system-prompts/{id}/                          │ partial_update│
    │ DELETE │ /system-prompts/{id}/                          │ destroy      │
    │ POST   │ /system-prompts/{id}/rate/                     │ rate         │
    │ POST   │ /system-prompts/{id}/duplicate/                 │ duplicate    │
    │ POST   │ /system-prompts/{id}/render/                    │ render       │
    │ GET    │ /system-prompts/by-category/{category}/        │ by_category  │
    │ GET    │ /system-prompts/search/                        │ search       │
    │ GET    │ /system-prompts/default/                       │ default      │
    └────────┴────────────────────────────────────────────────┴──────────────┘
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

from drf_spectacular.utils import extend_schema, extend_schema_view

from core.permissions import IsAdminOrReadOnly

from ...models import SystemPromptTemplate

from ..serializers import (
    SystemPromptSerializer,
    SystemPromptListSerializer,
    SystemPromptCreateSerializer,
    SystemPromptUpdateSerializer,
)


@extend_schema_view(
    list=extend_schema(
        tags=["System Prompts"], summary="List system prompt templates",
        description="Browse public and active system prompt templates.",
    ),
    retrieve=extend_schema(
        tags=["System Prompts"], summary="Retrieve template",
    ),
    create=extend_schema(
        tags=["System Prompts"], summary="Create template (admin)",
    ),
    partial_update=extend_schema(
        tags=["System Prompts"], summary="Update template (admin)",
    ),
    destroy=extend_schema(
        tags=["System Prompts"], summary="Delete template (admin)",
    ),
)
@extend_schema(tags=["System Prompts"])
class SystemPromptViewSet(viewsets.ModelViewSet):
    """
    CRUD + actions for SystemPromptTemplate.

    Any authenticated user can browse templates; only admins can
    create / update / delete them.
    """

    queryset = SystemPromptTemplate.objects.all()
    serializer_class = SystemPromptSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["category", "is_default", "is_public", "is_active"]
    search_fields = ["name", "description", "content"]
    ordering_fields = ["name", "usage_count", "created_at"]
    ordering = ["-is_default", "-usage_count", "name"]

    # ---- Serializer dispatch ----

    def get_serializer_class(self):
        mapping = {
            "list": SystemPromptListSerializer,
            "create": SystemPromptCreateSerializer,
            "update": SystemPromptUpdateSerializer,
            "partial_update": SystemPromptUpdateSerializer,
        }
        return mapping.get(self.action, SystemPromptSerializer)

    # ---- Queryset ----

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return SystemPromptTemplate.objects.none()

        qs = SystemPromptTemplate.objects.all()

        # Non-admins only see active public/default templates
        user = self.request.user
        if not (user.is_staff or user.is_superuser or user.role == "admin"):
            qs = SystemPromptTemplate.get_for_session()

        return qs

    # ---- Custom actions ----

    @extend_schema(
        summary="Rate template",
        description="Rate a system prompt template (1-5 stars).",
        request={
            "application/json": {
                "type": "object",
                "required": ["rating"],
                "properties": {
                    "rating": {"type": "integer", "minimum": 1, "maximum": 5},
                },
            }
        },
        responses={200: dict},
    )
    @action(detail=True, methods=["post"], url_path="rate")
    def rate(self, request, pk=None):
        """POST /system-prompts/{id}/rate/"""
        template = self.get_object()
        rating = request.data.get("rating")

        if rating is None:
            return Response(
                {"message": "Rating is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            rating = int(rating)
            new_avg = template.add_rating(rating)
            return Response({
                "message": "Rating added.",
                "average_rating": new_avg,
                "rating_count": template.rating_count,
            })
        except ValueError as e:
            return Response(
                {"message": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @extend_schema(
        summary="Duplicate template",
        description="Create a copy of this template.",
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                },
            }
        },
        responses={201: SystemPromptSerializer},
    )
    @action(detail=True, methods=["post"], url_path="duplicate")
    def duplicate(self, request, pk=None):
        """POST /system-prompts/{id}/duplicate/"""
        template = self.get_object()
        new_name = request.data.get("name")
        new_template = template.duplicate(new_name=new_name, user=request.user)
        serializer = SystemPromptSerializer(new_template)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Render template",
        description="Render the template with provided variables.",
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "variables": {
                        "type": "object",
                        "description": "Variable key-value pairs",
                    },
                },
            }
        },
        responses={200: dict},
    )
    @action(detail=True, methods=["post"], url_path="render")
    def render(self, request, pk=None):
        """POST /system-prompts/{id}/render/"""
        template = self.get_object()
        variables = request.data.get("variables", {})

        # Validate variables
        validation = template.validate_variables(variables)
        if not validation["valid"]:
            return Response(
                {
                    "message": "Missing required variables.",
                    "missing": validation["missing"],
                    "extra": validation["extra"],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        rendered = template.render(variables)
        return Response({
            "rendered_prompt": rendered,
            "variables_used": variables,
        })

    @extend_schema(
        summary="Templates by category",
        description="Get templates filtered by category.",
        responses={200: SystemPromptListSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="by-category/(?P<category>[^/.]+)")
    def by_category(self, request, category=None):
        """GET /system-prompts/by-category/{category}/"""
        templates = SystemPromptTemplate.get_by_category(category)
        serializer = SystemPromptListSerializer(templates, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Search templates",
        description="Search templates by name, description, or content.",
        responses={200: SystemPromptListSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request):
        """GET /system-prompts/search/?q=query"""
        query = request.query_params.get("q", "")
        if not query:
            return Response(
                {"message": "Query parameter 'q' is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        templates = SystemPromptTemplate.search_templates(query)
        page = self.paginate_queryset(templates)
        if page is not None:
            serializer = SystemPromptListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = SystemPromptListSerializer(templates, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Get default template",
        description="Return the platform-default system prompt template.",
        responses={200: SystemPromptSerializer},
    )
    @action(detail=False, methods=["get"], url_path="default")
    def default(self, request):
        """GET /system-prompts/default/"""
        template = SystemPromptTemplate.get_default()
        if not template:
            return Response(
                {"message": "No default template found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = SystemPromptSerializer(template)
        return Response(serializer.data)
