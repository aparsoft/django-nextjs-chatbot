# accounts/api/views/custom_user_views.py

"""
Action-based ViewSets for CustomUser and UserContact models.

Uses DRF DefaultRouter auto-discovery with @action decorators for
custom sub-routes.  Follows the skill patterns:
  - swagger_fake_view guard
  - select_related / prefetch_related for N+1 prevention
  - Operation-based serializer dispatch in get_serializer_class()
  - @extend_schema_view at class level + per-action @extend_schema
"""

from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django_filters.rest_framework import DjangoFilterBackend

from drf_spectacular.utils import extend_schema, extend_schema_view

from accounts.models.custom_user import UserContact

from ..serializers.custom_user_serializers import (
    CustomUserSerializer,
    CustomUserListSerializer,
    CustomUserCreateSerializer,
    CustomUserUpdateSerializer,
    UserContactSerializer,
    UserContactCreateSerializer,
    UserContactUpdateSerializer,
    PasswordChangeActionSerializer,
)
from ..serializers.response_serializers import AvatarResponseSerializer, MessageResponseSerializer

User = get_user_model()


# ---------------------------------------------------------------------------
#  CustomUser ViewSet
# ---------------------------------------------------------------------------


@extend_schema_view(
    list=extend_schema(tags=["Users"], summary="List users"),
    retrieve=extend_schema(tags=["Users"], summary="Retrieve user"),
    create=extend_schema(tags=["Users"], summary="Create user"),
    update=extend_schema(tags=["Users"], summary="Update user"),
    partial_update=extend_schema(tags=["Users"], summary="Partial update user"),
    destroy=extend_schema(tags=["Users"], summary="Delete user"),
)
@extend_schema(tags=["Users"])
class CustomUserViewSet(viewsets.ModelViewSet):
    """
    CRUD + custom actions for the CustomUser model.

    Auto-registered with the DefaultRouter as ``users/``.

    **Custom actions (auto-routed):**

    | Method | URL                              | Action           |
    |--------|----------------------------------|------------------|
    | GET    | /users/me/                       | me               |
    | GET    | /users/{id}/profile-image/       | profile_image    |
    | POST   | /users/{id}/verify-email/        | verify_email     |
    | POST   | /users/{id}/change-password/     | change_password  |
    | GET    | /users/stats/                    | stats            |
    """

    queryset = User.objects.all()
    serializer_class = CustomUserSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["role", "is_active", "email_verified"]
    search_fields = ["username", "email", "first_name", "last_name"]
    ordering_fields = ["date_joined", "last_active", "username", "email"]
    ordering = ["-date_joined"]

    # ---- Serializer dispatch ----

    def get_serializer_class(self):
        """Return the appropriate serializer for the current action."""
        mapping = {
            "list": CustomUserListSerializer,
            "create": CustomUserCreateSerializer,
            "update": CustomUserUpdateSerializer,
            "partial_update": CustomUserUpdateSerializer,
            "change_password": PasswordChangeActionSerializer,
        }
        return mapping.get(self.action, CustomUserSerializer)

    # ---- Queryset ----

    def get_queryset(self):
        """Scope queryset by role; eager-load related objects."""
        # Guard for drf-spectacular schema introspection
        if getattr(self, "swagger_fake_view", False):
            return User.objects.none()

        qs = User.objects.select_related("contact").all()

        user = self.request.user
        if user.is_staff or user.is_superuser or user.role == "admin":
            return qs

        # Regular users can only see themselves
        return qs.filter(id=user.id)

    # ---- Custom actions ----

    @extend_schema(
        summary="Get current user",
        description="Return the authenticated user's full profile.",
        responses={200: CustomUserSerializer},
    )
    @action(detail=False, methods=["get"], url_path="me", url_name="me")
    def me(self, request):
        """GET /users/me/ — current user's profile."""
        serializer = CustomUserSerializer(request.user, context={"request": request})
        return Response(serializer.data)

    @extend_schema(
        summary="Verify email",
        description="Manually verify a user's email address (admin only).",
        request=None,
        responses={200: MessageResponseSerializer},
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="verify-email",
        url_name="verify-email",
    )
    def verify_email(self, request, pk=None):
        """POST /users/{id}/verify-email/"""
        user = self.get_object()
        user.verify_email()
        return Response(
            {"message": "Email verified successfully", "status": "success"},
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Change password",
        description="Change password for a user. Requires current password verification.",
        request=PasswordChangeActionSerializer,
        responses={200: MessageResponseSerializer, 400: MessageResponseSerializer},
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="change-password",
        url_name="change-password",
    )
    def change_password(self, request, pk=None):
        """POST /users/{id}/change-password/"""
        user = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        current = serializer.validated_data["current_password"]
        new = serializer.validated_data["new_password"]

        if not user.check_password(current):
            return Response(
                {
                    "message": "Current password is incorrect",
                    "status": "error",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(new) < 8:
            return Response(
                {
                    "message": "New password must be at least 8 characters",
                    "status": "error",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new)
        user.save()
        return Response(
            {"message": "Password changed successfully", "status": "success"},
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Get profile image",
        description="Retrieve the user's profile avatar URL.",
        responses={200: AvatarResponseSerializer},
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="profile-image",
        url_name="profile-image",
    )
    def profile_image(self, request, pk=None):
        """GET /users/{id}/profile-image/"""
        user = self.get_object()

        from ...utils.profile_picture_utils import get_profile_picture_url

        url = get_profile_picture_url(user, request)
        if url:
            return Response(
                {"message": "Profile image found", "status": "success", "data": {"profile_picture_url": url}},
                status=status.HTTP_200_OK,
            )
        return Response(
            {"message": "No profile image found", "status": "info", "data": {"profile_picture_url": None}},
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="User statistics",
        description="Aggregate stats for users (admin only).",
        responses={200: dict},
    )
    @action(detail=False, methods=["get"], url_path="stats", url_name="stats")
    def stats(self, request):
        """GET /users/stats/ — aggregate user statistics."""
        qs = User.objects.all()
        return Response(
            {
                "total_users": qs.count(),
                "active_users": qs.filter(is_active=True).count(),
                "verified_users": qs.filter(email_verified=True).count(),
                "admin_users": qs.filter(role="admin").count(),
            }
        )


# ---------------------------------------------------------------------------
#  UserContact ViewSet
# ---------------------------------------------------------------------------


@extend_schema_view(
    list=extend_schema(tags=["User Contacts"], summary="List contacts"),
    retrieve=extend_schema(tags=["User Contacts"], summary="Retrieve contact"),
    create=extend_schema(tags=["User Contacts"], summary="Create contact"),
    update=extend_schema(tags=["User Contacts"], summary="Update contact"),
    partial_update=extend_schema(tags=["User Contacts"], summary="Partial update contact"),
    destroy=extend_schema(tags=["User Contacts"], summary="Delete contact"),
)
@extend_schema(tags=["User Contacts"])
class UserContactViewSet(viewsets.ModelViewSet):
    """
    CRUD for UserContact model.

    Auto-registered with the DefaultRouter as ``user-contacts/``.

    Regular users can only access their own contact record.
    """

    queryset = UserContact.objects.select_related("user", "country").all()
    serializer_class = UserContactSerializer
    permission_classes = [permissions.IsAuthenticated]

    # ---- Serializer dispatch ----

    def get_serializer_class(self):
        mapping = {
            "create": UserContactCreateSerializer,
            "update": UserContactUpdateSerializer,
            "partial_update": UserContactUpdateSerializer,
        }
        return mapping.get(self.action, UserContactSerializer)

    # ---- Queryset ----

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return UserContact.objects.none()

        qs = UserContact.objects.select_related("user", "country").all()

        user = self.request.user
        if user.is_staff or user.is_superuser or user.role == "admin":
            return qs

        return qs.filter(user=user)
