"""
Django admin configuration for chatbot app.
Imports all admin classes to register them with Django admin.
"""

from .chat_session_admin import ChatSessionAdmin

__all__ = [
    "ChatSessionAdmin",
]