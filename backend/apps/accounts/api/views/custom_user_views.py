# accounts/api/views/custom_user_views.py

"""
ViewSets for CustomUser and UserContact models.
"""

from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.db import models
from django_filters.rest_framework import DjangoFilterBackend

from drf_spectacular.utils import extend_schema, extend_schema_view

from ..serializers.custom_user_serializers import (
    CustomUserSerializer,
    CustomUserMinimalSerializer,
    UserContactSerializer,
    UserContactMinimalSerializer,
)
from ..serializers.response_serializers import AvatarResponseSerializer

User = get_user_model()


@extend_schema_view(
    list=extend_schema(tags=["Users"], summary="List users"),
    retrieve=extend_schema(tags=["Users"], summary="Get user details"),
    create=extend_schema(tags=["Users"], summary="Create user"),
    update=extend_schema(tags=["Users"], summary="Update user"),
    partial_update=extend_schema(tags=["Users"], summary="Partial update user"),
    destroy=extend_schema(tags=["Users"], summary="Delete user"),
)
class CustomUserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for CustomUser model.

    Provides CRUD operations and additional actions for user management.
    Non-admin users can only see their own record.
    """

    queryset = User.objects.all()
    serializer_class = CustomUserSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["role", "is_active", "email_verified"]
    search_fields = ["username", "email", "first_name", "last_name"]
    ordering_fields = ["date_joined", "last_active", "username", "email"]

    def get_serializer_class(self):
        if self.action == "list":
            return CustomUserMinimalSerializer
        return CustomUserSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = User.objects.all()

        if user.is_staff or user.is_superuser or user.role == "admin":
            return queryset

        # Regular users can only see themselves
        return queryset.filter(id=user.id)

    @extend_schema(
        tags=["Users"],
        summary="Get current user",
        description="Return the authenticated user's profile.",
        responses={200: CustomUserSerializer},
    )
    @action(detail=False, methods=["get"])
    def me(self, request):
        """Get the authenticated user's profile."""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @extend_schema(
        tags=["Users"],
        summary="Verify email",
        description="Manually verify a user's email address (admin only).",
        responses={200: {"type": "object", "properties": {"message": {"type": "string"}}}},
    )
    @action(detail=True, methods=["post"])
    def verify_email(self, request, pk=None):
        """Verify user's email address."""
        user = self.get_object()
        user.verify_email()
        return Response({"message": "Email verified successfully"}, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Users"],
        summary="Get profile image",
        description="Compatibility endpoint — delegates to ProfileAvatarView.",
        responses={200: AvatarResponseSerializer},
    )
    @action(detail=False, methods=["get"])
    def profile_image(self, request):
        """Get current user's profile image URL."""
        from ..views.profile_avatar_views import ProfileAvatarView

        avatar_view = ProfileAvatarView()
        avatar_view.request = request
        return avatar_view.get(request)


@extend_schema_view(
    list=extend_schema(tags=["User Contacts"], summary="List contacts"),
    retrieve=extend_schema(tags=["User Contacts"], summary="Get contact details"),
    create=extend_schema(tags=["User Contacts"], summary="Create contact"),
    update=extend_schema(tags=["User Contacts"], summary="Update contact"),
    partial_update=extend_schema(tags=["User Contacts"], summary="Partial update contact"),
    destroy=extend_schema(tags=["User Contacts"], summary="Delete contact"),
)
class UserContactViewSet(viewsets.ModelViewSet):
    """
    ViewSet for UserContact model.

    Provides CRUD operations for user contact information.
    Regular users can only see their own contact.
    """

    queryset = User.objects.all()
    serializer_class = UserContactSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "list":
            return UserContactMinimalSerializer
        return UserContactSerializer

    def get_queryset(self):
        from accounts.models.custom_user import UserContact

        user = self.request.user

        if user.is_staff or user.is_superuser or user.role == "admin":
            return UserContact.objects.all()

        return UserContact.objects.filter(user=user)
