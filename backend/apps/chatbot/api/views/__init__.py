"""
Chatbot API ViewSets package.

ViewSet             | Model                 | Permission         | Router prefix
--------------------|-----------------------|--------------------|------------------
ChatAgentViewSet    | — (not model-backed)  | IsOwnerOrAdmin     | chat-agent
ChatSessionViewSet  | ChatSession           | IsOwnerOrAdmin     | chat-sessions
UserPreferenceViewSet | UserPreference      | IsOwnerOrAdmin     | preferences
TokenUsageViewSet   | TokenUsage            | IsOwnerOrAdmin     | token-usage
MessageFeedbackViewSet | MessageFeedback    | IsOwnerOrAdmin     | message-feedback
UserDocumentViewSet | UserDocument          | IsOwnerOrAdmin     | documents
SystemPromptViewSet | SystemPromptTemplate  | IsAdminOrReadOnly  | system-prompts
UserToolViewSet     | UserTool              | IsOwnerOrAdmin     | tools
UserAPIKeyViewSet   | UserAPIKey            | IsOwnerOrAdmin     | api-keys
"""

from .chat_agent_views import ChatAgentViewSet
from .chat_session_views import ChatSessionViewSet
from .user_preference_views import UserPreferenceViewSet
from .token_usage_views import TokenUsageViewSet
from .message_feedback_views import MessageFeedbackViewSet
from .user_document_views import UserDocumentViewSet
from .system_prompt_views import SystemPromptViewSet
from .user_tool_views import UserToolViewSet
from .user_api_key_views import UserAPIKeyViewSet

__all__ = [
    "ChatAgentViewSet",
    "ChatSessionViewSet",
    "UserPreferenceViewSet",
    "TokenUsageViewSet",
    "MessageFeedbackViewSet",
    "UserDocumentViewSet",
    "SystemPromptViewSet",
    "UserToolViewSet",
    "UserAPIKeyViewSet",
]
