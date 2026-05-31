"""
Core permissions package for the AI chatbot application.

Permission classes enforce data isolation — every user accesses only
their own chat sessions, documents, preferences, tools, API keys,
token usage, and feedback.  Admins can see and manage everything.

Quick reference:
    IsOwnerOrAdmin   → Main workhorse: owner + admin (most ViewSets)
    IsOwner          → Strict owner-only, no admin bypass (sensitive ops)
    IsAdminOrReadOnly → Read for all authenticated, write for admins
    IsAdminUser      → Admin-only endpoints (stats, dashboards)

Usage in ViewSets::

    from core.permissions import IsOwnerOrAdmin, IsAdminOrReadOnly

    class ChatSessionViewSet(viewsets.ModelViewSet):
        permission_classes = [IsOwnerOrAdmin]

    class SystemPromptViewSet(viewsets.ModelViewSet):
        permission_classes = [IsAdminOrReadOnly]
"""

from .base import (
    IsOwnerOrAdmin,
    IsOwner,
    IsAdminOrReadOnly,
    IsAdminUser,
)

__all__ = [
    "IsOwnerOrAdmin",
    "IsOwner",
    "IsAdminOrReadOnly",
    "IsAdminUser",
]
