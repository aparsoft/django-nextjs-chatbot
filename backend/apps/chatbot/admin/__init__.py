"""
Django admin configuration for chatbot app.
Imports all admin classes to register them with Django admin.
"""

from .chat_session_admin import ChatSessionAdmin
from .message_feedback_admin import MessageFeedbackAdmin

__all__ = [
    "ChatSessionAdmin",
    "MessageFeedbackAdmin",
]