"""
Core permission classes for the AI chatbot application.

This is a single-user chatbot — every user accesses only their own
data (chat sessions, documents, preferences, tools, API keys, token
usage, feedback).  Admins can see and manage everything.

Permission matrix:
    ┌─────────────────────────┬──────────────┬──────────┬───────────┐
    │ Model                   │ Owner (user) │ Admin    │ Other     │
    ├─────────────────────────┼──────────────┼──────────┼───────────┤
    │ ChatSession             │ CRUD own     │ CRUD all │ deny      │
    │ UserPreference          │ CRUD own     │ CRUD all │ deny      │
    │ TokenUsage              │ Read own     │ CRUD all │ deny      │
    │ MessageFeedback         │ CRUD own     │ CRUD all │ deny      │
    │ UserDocument            │ CRUD own     │ CRUD all │ deny      │
    │ SystemPromptTemplate    │ Read active  │ CRUD all │ deny      │
    │ UserTool                │ CRUD own     │ CRUD all │ deny      │
    │ UserAPIKey              │ CRUD own     │ CRUD all │ deny      │
    └─────────────────────────┴──────────────┴──────────┴───────────┘

How to use in ViewSets:
    class MyViewSet(viewsets.ModelViewSet):
        permission_classes = [IsOwnerOrAdmin]

        def get_queryset(self):
            # Scope to owner — permissions are a safety net on top
            qs = MyModel.objects.filter(user=self.request.user)
            if self.request.user.role == "admin":
                qs = MyModel.objects.all()
            return qs

The queryset filters FIRST (list-level); permissions add object-level
checks (detail/update/delete) as a second layer of defence.
"""

from rest_framework.permissions import BasePermission, SAFE_METHODS


# ---------------------------------------------------------------------------
#  Helper
# ---------------------------------------------------------------------------


def _is_admin(user) -> bool:
    """Return True if the user has admin-level access."""
    return bool(
        user
        and user.is_authenticated
        and (user.role == "admin" or user.is_staff or user.is_superuser)
    )


def _get_owner(obj, request):
    """
    Resolve the owner user from an object.

    Walks common relationship patterns so the permission class works
    across every chatbot model without subclassing:

      1. obj.user          — ChatSession, TokenUsage, UserDocument,
                              UserTool, UserAPIKey, MessageFeedback
      2. obj.user_id       — same models (avoids DB fetch)

    Returns the User instance/id or None if the object has no owner.
    """
    # Direct FK (most models)
    owner = getattr(obj, "user", None)
    if owner is not None:
        return owner

    # OneToOne reverse (e.g. UserContact → user)
    # Some objects may not have a .user at all (SystemPromptTemplate)
    return None


# ---------------------------------------------------------------------------
#  Permission Classes
# ---------------------------------------------------------------------------


class IsOwnerOrAdmin(BasePermission):
    """
    Allow access if the requesting user owns the object OR is an admin.

    **Owner check:** `obj.user == request.user`  (object-level).

    Works with any model that has a ``user`` ForeignKey / OneToOneField.

    Usage::

        class ChatSessionViewSet(viewsets.ModelViewSet):
            permission_classes = [IsOwnerOrAdmin]

            def get_queryset(self):
                qs = ChatSession.objects.all()
                if not _is_admin(self.request.user):
                    qs = qs.filter(user=self.request.user)
                return qs

    Note:
        ``has_object_permission`` is NOT called for list/create actions
        (there is no single object to check).  Scope the queryset in
        ``get_queryset()`` for those cases.
    """

    def has_permission(self, request, view):
        """Authenticated users only."""
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        """Admins bypass; otherwise the requesting user must own the object."""
        if _is_admin(request.user):
            return True

        owner = _get_owner(obj, request)
        if owner is None:
            # Object has no owner field (e.g. SystemPromptTemplate) — deny
            return False

        # Support both User instance and user-id comparison
        if hasattr(owner, "pk"):
            return owner.pk == request.user.pk
        return owner == request.user.pk


class IsOwner(BasePermission):
    """
    Strict owner-only access — no admin bypass.

    Use for the most sensitive operations where even admins should
    not have access (e.g., viewing decrypted API keys, deleting
    critical personal data).

    Usage::

        class UserAPIKeyViewSet(viewsets.ModelViewSet):
            permission_classes = [IsOwner]
    """

    def has_permission(self, request, view):
        """Authenticated users only."""
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        """The requesting user MUST own the object — no exceptions."""
        owner = _get_owner(obj, request)
        if owner is None:
            return False

        if hasattr(owner, "pk"):
            return owner.pk == request.user.pk
        return owner == request.user.pk


class IsAdminOrReadOnly(BasePermission):
    """
    Authenticated users can READ; only admins can WRITE.

    Perfect for shared, platform-level resources like
    SystemPromptTemplate where every logged-in user can browse
    templates but only admins create/edit/delete them.

    Usage::

        class SystemPromptViewSet(viewsets.ModelViewSet):
            permission_classes = [IsAdminOrReadOnly]
    """

    def has_permission(self, request, view):
        """Authenticated users can read; only admins can write."""
        if not (request.user and request.user.is_authenticated):
            return False

        if request.method in SAFE_METHODS:
            return True

        return _is_admin(request.user)


class IsAdminUser(BasePermission):
    """
    Admin-only access — no regular user access at all.

    Use for management dashboards, platform-wide stats, bulk
    operations, and other admin-only endpoints.

    Usage::

        @action(detail=False, methods=["get"], url_path="stats")
        def stats(self, request):
            ...
        # Or set on the ViewSet:
        permission_classes = [IsAdminUser]
    """

    def has_permission(self, request, view):
        """Only admin users are allowed."""
        return _is_admin(request.user)
