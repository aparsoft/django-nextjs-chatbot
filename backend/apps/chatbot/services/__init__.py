"""
chatbot.services

Service layer for chatbot app. Provides unified access to all core service classes:

- AgentService: LangGraph ReAct agent with PGVector memory (façade)
- ChatAgentOrchestrator: Full orchestrator around create_react_agent
- APIKeyService: Manage user API keys
- ChatSessionService: Manage chat sessions and threads
- DocumentProcessingService: Process uploaded documents
- MessageService: Manage conversation messages
- SummarizationService: Automatic conversation summarization
- TokenUsageService: Track and analyze token usage
- ToolService: Manage user tools
- UserPreferenceService: Manage user AI preferences
- VectorStorageService: PGVector operations for embeddings and search

Usage:
        from chatbot.services import AgentService, ChatAgentOrchestrator
        from chatbot.services import APIKeyService, ChatSessionService, ...
"""

from .agent_service import AgentService, ChatAgentOrchestrator
from .api_key_service import APIKeyService
from .chat_session_service import ChatSessionService
from .document_processing_service import DocumentProcessingService
from .message_service import MessageService
from .summarization_service import SummarizationService
from .token_usage_service import TokenUsageService
from .tool_service import ToolService
from .user_preference_service import UserPreferenceService
from .vector_storage_service import VectorStorageService
