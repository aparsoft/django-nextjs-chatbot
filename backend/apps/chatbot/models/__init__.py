"""
Chatbot Models Package

This package contains all Django models for the AI chatbot application.
Each model follows the "fatty model, thin viewset" pattern — business
logic lives on the model, and viewsets delegate to class/instance methods.

Model index
-----------
- :class:`ChatSession`       — conversation metadata mapped to LangGraph threads
- :class:`UserPreference`    — per-user AI settings and session defaults
- :class:`TokenUsage`         — per-request token counts, costs, and analytics
- :class:`MessageFeedback`    — user ratings and issue reports on AI messages
- :class:`UserDocument`       — uploaded file metadata with RAG processing state
- :class:`SystemPromptTemplate` — named, parameterised system prompts
- :class:`UserTool`           — per-user tool enable/disable and configuration
- :class:`UserAPIKey`         — encrypted third-party API keys with quotas

Data ownership split
--------------------
Django models (this package):
  ✓ User-facing metadata (titles, descriptions, tags)
  ✓ User preferences and settings
  ✓ Usage tracking, billing, and quotas
  ✓ Tool configurations and API keys
  ✓ File upload metadata and processing state
  ✓ Feedback and analytics

LangGraph Checkpointer (``langchain_history`` database):
  ✓ Message history and conversation state
  ✓ Thread/checkpoint management
  ✓ Automatic summarisation

PGVector store (``langchain_pgvector`` database):
  ✓ Document embeddings for RAG
  ✓ Semantic search on documents

Important: don't duplicate what LangGraph or pgvector already manages!
"""

# Core conversation models
from .chat_session import ChatSession
from .user_preference import UserPreference
from .message_feedback import MessageFeedback

# Usage and analytics
from .token_usage import TokenUsage

# Document and RAG
from .user_document import UserDocument

# System configuration
from .system_prompt import SystemPromptTemplate
from .user_tool import UserTool, TOOL_REGISTRY
from .user_api_key import UserAPIKey

# Export all models
__all__ = [
    # Core
    "ChatSession",
    "UserPreference",
    "MessageFeedback",
    # Analytics
    "TokenUsage",
    # RAG
    "UserDocument",
    # Configuration
    "SystemPromptTemplate",
    "UserTool",
    "TOOL_REGISTRY",
    "UserAPIKey",
]
