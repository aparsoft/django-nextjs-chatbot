"""
Agent Service — LangGraph ReAct Agent with PGVector Memory

Builds a production-ready ``create_agent`` graph (from ``langchain.agents``)
backed by ``PostgresSaver`` for conversation checkpointing.  Wraps everything
in an orchestrator that wires together:

- LLM (via ``"openai:gpt-4o-mini"`` model strings or ChatOpenAI instances)
- PostgresSaver checkpointer (PG_CHECKPOINT_URI)
- SummarizationMiddleware (compresses long conversations before LLM calls)
- ToolService (loads enabled LangChain tools)
- VectorStorageService (RAG document retrieval as a tool)

Uses the **latest LangChain v1.x / LangGraph v1.x** API:
    - ``langchain.agents.create_agent`` (replaces deprecated ``create_react_agent``)
    - ``system_prompt=`` (replaces ``prompt=``)
    - ``middleware=`` (replaces ``pre_model_hook=`` / ``post_model_hook=``)

Usage:
    from chatbot.services import AgentService

    # One-shot convenience
    result = AgentService.chat(session, "Hello, who are you?")

    # Full orchestrator (for streaming / multi-turn)
    orchestrator = AgentService.create_orchestrator(session)
    result = orchestrator.invoke("Tell me about Python")

Architecture:
    ┌──────────────────────────────────────────────────────────┐
    │                  ChatAgentOrchestrator                   │
    │  ┌────────────────────────────────────────────────────┐  │
    │  │   create_agent (langchain.agents — LangChain v1)   │  │
    │  │   ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │  │
    │  │   │   LLM    │→ │  Tools   │→ │  PostgresSaver   │ │  │
    │  │   └──────────┘  └──────────┘  └──────────────────┘ │  │
    │  │   middleware: [SummarizationMiddleware]            │  │
    │  │   system_prompt: session-based                     │  │
    │  └────────────────────────────────────────────────────┘  │
    │  + session analytics, token tracking                     │
    └──────────────────────────────────────────────────────────┘
"""

import logging
from typing import Any, Dict, List, Optional, TypedDict

from django.conf import settings
from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.tools import tool as lc_tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from ..models import ChatSession
from .summarization_service import SummarizationService
from .tool_service import ToolService
from .vector_storage_service import VectorStorageService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Summarization Middleware — compresses long conversations before LLM calls
# ---------------------------------------------------------------------------


class SummarizationMiddleware(AgentMiddleware):
    """
    Middleware that compresses conversation history before each LLM call.

    Replaces the old ``pre_model_hook`` pattern with the composable
    middleware system introduced in LangChain v1.x.

    How it works:
        1. ``before_model`` is called before every LLM invocation
        2. If the conversation exceeds the token threshold, older
           messages are summarized into a single SystemMessage
        3. Recent messages are kept intact for continuity

    Usage (automatically wired by ChatAgentOrchestrator)::

        from langchain.agents import create_agent

        agent = create_agent(
            model="openai:gpt-4o-mini",
            tools=[...],
            middleware=[SummarizationMiddleware(session)],
            checkpointer=checkpointer,
        )
    """

    def __init__(self, session: ChatSession):
        self._session = session
        self._config = SummarizationService.get_session_config(session)

    def before_model(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compress messages before sending to the LLM.

        This is the middleware equivalent of the old ``pre_model_hook``.
        """
        if not self._config.get("enabled", True):
            return state

        messages = state.get("messages", [])

        if not SummarizationService.should_summarize(
            messages, self._config.get("threshold", 384)
        ):
            return state

        compressed = SummarizationService.compress_messages(
            messages=messages,
            keep_recent=self._config.get("keep_recent", 10),
            model_name=self._config.get("model_name", "gpt-4o-mini"),
            max_summary_tokens=self._config.get("max_summary_tokens", 128),
            style=self._config.get("style", "concise"),
        )

        logger.info(
            "SummarizationMiddleware: compressed %d → %d messages",
            len(messages),
            len(compressed),
        )

        return {**state, "messages": compressed}


# ---------------------------------------------------------------------------
# Built-in LangChain tools the agent can use
# ---------------------------------------------------------------------------


@lc_tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression and return the result.

    Use this tool for any arithmetic, algebra, or math-related queries.

    Args:
        expression: A valid Python math expression (e.g. "2 + 2", "15 * 3.5").
    """
    try:
        # Safe evaluation — only allow math operations
        allowed = {
            "abs": abs,
            "round": round,
            "min": min,
            "max": max,
            "pow": pow,
            "sum": sum,
        }
        result = eval(expression, {"__builtins__": {}}, allowed)  # noqa: S307
        return str(result)
    except Exception as e:
        return f"Error evaluating expression: {e}"


def _make_document_retriever_tool(user):
    """Create a document retrieval tool scoped to a specific user."""

    @lc_tool
    def document_retriever(query: str) -> str:
        """Search through the user's uploaded documents using semantic search.

        Use this when the user asks questions that might be answered by
        documents they have previously uploaded.

        Args:
            query: Natural-language search query.
        """
        try:
            results = VectorStorageService.semantic_search(
                query=query,
                user=user,
                k=5,
            )
            if not results:
                return "No relevant documents found."
            return VectorStorageService.format_search_results_for_context(
                results,
                max_context_length=3000,
            )
        except Exception as e:
            logger.warning("document_retriever tool error: %s", e)
            return f"Error searching documents: {e}"

    return document_retriever


# ---------------------------------------------------------------------------
# Tool loading
# ---------------------------------------------------------------------------

_BUILTIN_TOOLS = {
    "calculator": lambda _user: calculator,
    "document_retriever": _make_document_retriever_tool,
    # web_search and code_executor are placeholders — they require external
    # services (Tavily API, sandbox) so we return None and skip them.
    "web_search": lambda _user: None,
    "code_executor": lambda _user: None,
}


def load_tools_for_user(user) -> List:
    """
    Build a list of LangChain ``BaseTool`` instances for every tool the
    user has enabled in their ``UserTool`` records.
    """
    user_tools = ToolService.get_user_tools(user, enabled_only=True)
    tools: List = []

    for ut in user_tools:
        factory = _BUILTIN_TOOLS.get(ut.tool_name)
        if factory is None:
            logger.debug("Skipping unimplemented tool: %s", ut.tool_name)
            continue
        instance = factory(user)
        if instance is not None:
            tools.append(instance)

    return tools


# ---------------------------------------------------------------------------
# Checkpointer singleton (connection-pool backed)
# ---------------------------------------------------------------------------
# Using a psycopg ConnectionPool instead of a single Connection prevents
# "the connection is closed" errors.  A single connection can be dropped by
# the server (idle timeout, network hiccup, etc.) and never recovers.
# A pool automatically replaces broken connections.

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_pool: Optional[ConnectionPool] = None
_checkpointer: Optional[PostgresSaver] = None


def get_checkpointer() -> PostgresSaver:
    """
    Return a ``PostgresSaver`` backed by a ``ConnectionPool``.

    The pool handles reconnection automatically, so this is safe for
    long-running processes (Django runserver, Celery workers, etc.).
    """
    global _pool, _checkpointer
    if _checkpointer is None:
        _pool = ConnectionPool(
            conninfo=settings.PG_CHECKPOINT_URI,
            min_size=2,
            max_size=10,
            kwargs={"autocommit": True, "row_factory": dict_row},
            open=True,
        )
        _checkpointer = PostgresSaver(_pool)
        _checkpointer.setup()
        logger.info("PostgresSaver checkpointer initialised (pool-backed)")
    return _checkpointer


# ---------------------------------------------------------------------------
# ChatAgentOrchestrator — the main entry-point for agent interaction
# ---------------------------------------------------------------------------


class ChatAgentOrchestrator:
    """
    High-level orchestrator that owns a compiled ``create_agent`` graph
    and provides ``invoke`` / ``stream`` methods.

    Uses the **latest LangChain v1.x** API:
        - ``create_agent`` from ``langchain.agents``
        - ``system_prompt=`` instead of ``prompt=``
        - ``middleware=`` instead of ``pre_model_hook=``

    Usage::

        orchestrator = ChatAgentOrchestrator(session)
        result = orchestrator.invoke("What is 2 + 2?")
        print(result["response"])
    """

    def __init__(
        self,
        session: ChatSession,
        system_prompt: Optional[str] = None,
        recursion_limit: int = 25,
    ):
        self.session = session
        self.user = session.user
        self.recursion_limit = recursion_limit

        # Tools for this user
        self.tools = load_tools_for_user(self.user)

        # Checkpointer (PostgresSaver singleton)
        self.checkpointer = get_checkpointer()

        # Middleware — summarization before LLM calls
        self.middleware = [SummarizationMiddleware(session)]

        # System prompt
        self.system_prompt = system_prompt or self._build_system_prompt()

        # Build the compiled agent graph using the NEW create_agent API
        self.agent = create_agent(
            model=f"openai:{session.model_name}",
            tools=self.tools,
            system_prompt=self.system_prompt,
            middleware=self.middleware,
            checkpointer=self.checkpointer,
        )

        # LangGraph config (thread_id == session.id)
        self.config: Dict[str, Any] = {
            "configurable": {"thread_id": session.thread_id},
            "recursion_limit": self.recursion_limit,
        }

    # ------------------------------------------------------------------
    # System prompt builder
    # ------------------------------------------------------------------

    def _build_system_prompt(self) -> str:
        """Compose a default system prompt from user preferences."""
        base = (
            "You are a helpful, knowledgeable AI assistant. "
            "Be concise, accurate, and friendly.\n\n"
            "Guidelines:\n"
            "- Answer questions clearly and directly.\n"
            "- If you use a tool, explain what you found.\n"
            "- If you don't know something, say so honestly.\n"
        )
        try:
            prefs = self.user.ai_preferences
            custom = getattr(prefs, "custom_system_prompt", None)
            if custom:
                base = custom
        except Exception:
            pass

        return base

    # ------------------------------------------------------------------
    # Invoke (synchronous — one-shot)
    # ------------------------------------------------------------------

    def invoke(self, user_message: str) -> Dict[str, Any]:
        """
        Send a user message and return the agent's response.

        Args:
            user_message: The human's message text.

        Returns:
            dict with keys:
                - response (str): the assistant's reply text
                - messages (list[BaseMessage]): full conversation turn
                - session (ChatSession): the updated session
                - tokens_used (int): approximate tokens consumed
        """
        logger.info(
            "Agent invoke: session=%s, msg_len=%d",
            self.session.thread_id,
            len(user_message),
        )

        result = self.agent.invoke(
            {"messages": [HumanMessage(content=user_message)]},
            config=self.config,
        )
        logger.debug("Agent invoke result: %s", result)

        # Extract the last AI message as the response
        ai_response = ""
        for msg in reversed(result.get("messages", [])):
            if isinstance(msg, AIMessage):
                ai_response = msg.content
                break
        logger.info("Agent response length: %d", len(ai_response))
        # Update session analytics
        self.session.update_analytics(message_count=2)  # human + assistant

        # Auto-title on first exchange
        if self.session.title == "New Conversation":
            self.session.update_title(user_message)

        # Extract token usage from the last AI message (if available)
        tokens_used = 0
        messages = result.get("messages", [])
        if messages and messages[-1] is not None:
            usage = getattr(messages[-1], "usage_metadata", None)
            if usage:
                tokens_used = usage.get("total_tokens", 0)

        return {
            "response": ai_response,
            "messages": messages,
            "session": self.session,
            "tokens_used": tokens_used,
        }

    # ------------------------------------------------------------------
    # Stream (generator — for WebSocket / SSE)
    # ------------------------------------------------------------------

    def stream(self, user_message: str):
        """
        Yield LangGraph stream events for real-time output.

        Usage::

            for event in orchestrator.stream("Hello"):
                print(event)
        """
        logger.info(
            "Agent stream: session=%s, msg_len=%d",
            self.session.thread_id,
            len(user_message),
        )

        for event in self.agent.stream(
            {"messages": [HumanMessage(content=user_message)]},
            config=self.config,
            stream_mode="values",
        ):
            yield event

        # Update analytics after streaming completes
        self.session.update_analytics(message_count=2)
        if self.session.title == "New Conversation":
            self.session.update_title(user_message)

    # ------------------------------------------------------------------
    # Chat history helpers
    # ------------------------------------------------------------------

    def get_history(self) -> List[BaseMessage]:
        """Return the current conversation history from the checkpointer."""
        checkpoint_tuple = self.checkpointer.get_tuple(self.config)
        if checkpoint_tuple is None:
            return []
        return checkpoint_tuple.checkpoint.get("channel_values", {}).get("messages", [])

    def get_history_display(self) -> List[Dict[str, Any]]:
        """Return formatted conversation history for display."""
        from .message_service import MessageService

        messages = self.get_history()
        return MessageService.format_messages_for_display(messages)


# ---------------------------------------------------------------------------
# Convenience class-level API (AgentService.chat(...))
# ---------------------------------------------------------------------------


class AgentService:
    """
    Stateless façade over ``ChatAgentOrchestrator``.

    Most call-sites only need to send one message and get a reply, so
    this class provides a one-liner API without managing an orchestrator
    instance.

    Usage::

        result = AgentService.chat(session, "What is LangGraph?")
        print(result["response"])

        # With streaming
        for event in AgentService.chat_stream(session, "Hello"):
            print(event)

        # Direct access to the orchestrator for advanced use
        orchestrator = AgentService.create_orchestrator(session)
    """

    @staticmethod
    def create_orchestrator(
        session: ChatSession,
        system_prompt: Optional[str] = None,
        recursion_limit: int = 25,
    ) -> ChatAgentOrchestrator:
        """
        Create and return a ``ChatAgentOrchestrator`` for the given session.

        Args:
            session: ChatSession instance (provides user, model, temperature).
            system_prompt: Override the default system prompt.
            recursion_limit: Max agent steps before stopping.

        Returns:
            A ready-to-use ``ChatAgentOrchestrator``.
        """
        return ChatAgentOrchestrator(
            session=session,
            system_prompt=system_prompt,
            recursion_limit=recursion_limit,
        )

    @staticmethod
    def chat(
        session: ChatSession,
        user_message: str,
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        One-shot convenience: send a message, get the AI response.

        Args:
            session: ChatSession to chat in.
            user_message: The user's message.
            system_prompt: Optional system prompt override.

        Returns:
            dict with response, messages, session, tokens_used.
        """
        orchestrator = AgentService.create_orchestrator(
            session=session,
            system_prompt=system_prompt,
        )
        return orchestrator.invoke(user_message)

    @staticmethod
    def chat_stream(session: ChatSession, user_message: str):
        """
        Streaming convenience: yields LangGraph events.

        Args:
            session: ChatSession to chat in.
            user_message: The user's message.

        Yields:
            LangGraph stream events (dicts).
        """
        orchestrator = AgentService.create_orchestrator(session=session)
        yield from orchestrator.stream(user_message)
