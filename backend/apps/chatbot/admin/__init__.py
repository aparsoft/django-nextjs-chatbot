"""
Django admin configuration for chatbot app.
Imports all admin classes to register them with Django admin.
"""

from .chat_session_admin import ChatSessionAdmin
from .message_feedback_admin import MessageFeedbackAdmin
from .system_prompt_admin import SystemPromptTemplateAdmin
from .token_usage_admin import TokenUsageAdmin
from .user_api_key_admin import UserAPIKeyAdmin
from .user_document_admin import UserDocumentAdmin
from .user_preference_admin import UserPreferenceAdmin
from .user_tool_admin import UserToolAdmin

__all__ = [
    "ChatSessionAdmin",
    "MessageFeedbackAdmin",
    "SystemPromptTemplateAdmin",
    "TokenUsageAdmin",
    "UserAPIKeyAdmin",
    "UserDocumentAdmin",
    "UserPreferenceAdmin",
    "UserToolAdmin",
]
