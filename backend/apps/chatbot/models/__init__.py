"""
Chatbot Models Package

This package contains all Django models for the AI chatbot application.

Model Organization:
-------------------
1. ChatSession - User conversation threads (maps to LangGraph thread_id)
2. UserPreference - AI settings and user preferences
3. TokenUsage - Track AI token consumption and costs
4. MessageFeedback - User ratings and feedback on AI responses
5. UserDocument - File uploads for RAG (Retrieval Augmented Generation)
6. SystemPromptTemplate - Reusable system prompts
7. UserTool - Custom tools/functions users can enable
8. UserAPIKey - Encrypted user API keys

Important Notes:
----------------
- Message history is stored by LangGraph's PostgresCheckpointer (PG_CHECKPOINT_URI)
- Document embeddings are stored in pgvector (PGVECTOR_CONNECTION_STRING)
- These Django models store metadata, user preferences, and analytics
- Don't duplicate what LangGraph already manages!
- Tool definitions live in TOOL_REGISTRY (user_tool.py), NOT in a separate model

Architecture:
-------------
Django Models (this package):
  ✓ User-facing metadata (titles, descriptions)
  ✓ User preferences and settings
  ✓ Usage tracking and billing
  ✓ Tool configurations
  ✓ File upload metadata
  ✓ Feedback and analytics

LangGraph Checkpointer (PG_CHECKPOINT_URI):
  ✓ Message history and conversation state
  ✓ Thread/checkpoint management
  ✓ Automatic summarization

PGVector Store (PGVECTOR_CONNECTION_STRING):
  ✓ Document embeddings for RAG
  ✓ Semantic search on documents
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
    'ChatSession',
    'UserPreference',
    'MessageFeedback',

    # Analytics
    'TokenUsage',

    # RAG
    'UserDocument',

    # Configuration
    'SystemPromptTemplate',
    'UserTool',
    'TOOL_REGISTRY',
    'UserAPIKey',
]
