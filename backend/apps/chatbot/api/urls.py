"""
Chatbot API URL configuration.

All ViewSets are registered with DefaultRouter for automatic
URL discovery.  Mounted at /api/v1/chatbot/ in config/urls.py.
"""

from rest_framework.routers import DefaultRouter

from .views import (
    ChatAgentViewSet,
    ChatSessionViewSet,
    UserPreferenceViewSet,
    TokenUsageViewSet,
    MessageFeedbackViewSet,
    UserDocumentViewSet,
    SystemPromptViewSet,
    UserToolViewSet,
    UserAPIKeyViewSet,
)

router = DefaultRouter()

# ── Chat Agent ───────────────────────────────────────────────────────
router.register(r"chat-agent", ChatAgentViewSet, basename="chat-agent")

# ── Core conversation ────────────────────────────────────────────────
router.register(r"chat-sessions", ChatSessionViewSet, basename="chat-session")
router.register(r"preferences", UserPreferenceViewSet, basename="user-preference")
router.register(r"message-feedback", MessageFeedbackViewSet, basename="message-feedback")

# ── Analytics ────────────────────────────────────────────────────────
router.register(r"token-usage", TokenUsageViewSet, basename="token-usage")

# ── Documents & RAG ─────────────────────────────────────────────────
router.register(r"documents", UserDocumentViewSet, basename="user-document")

# ── Configuration ────────────────────────────────────────────────────
router.register(r"system-prompts", SystemPromptViewSet, basename="system-prompt")
router.register(r"tools", UserToolViewSet, basename="user-tool")
router.register(r"api-keys", UserAPIKeyViewSet, basename="user-api-key")

urlpatterns = router.urls
