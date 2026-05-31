"""
Agent Service — LangGraph ReAct Agent with PGVector Memory

Builds a production-ready ``create_react_agent`` graph backed by
``PostgresSaver`` for conversation checkpointing.  Wraps everything in
an orchestrator that wires together:

- LLM (ChatOpenAI via session model_name / temperature)
- PostgresSaver checkpointer (PG_CHECKPOINT_URI)
- SummarizationService (as pre_model_hook)
- ToolService (loads enabled LangChain tools)
- VectorStorageService (RAG document retrieval as a tool)

Usage:
    from chatbot.services import AgentService

    # One-shot convenience
    result = AgentService.chat(session, "Hello, who are you?")

    # Full orchestrator (for streaming / multi-turn)
    orchestrator = AgentService.create_orchestrator(session)
    result = orchestrator.invoke("Tell me about Python")

Architecture:
    ┌────────────────────────────────────────────────┐
    │                ChatAgentOrchestrator           │
    │  ┌──────────────────────────────────────────┐  │
    │  │   create_react_agent (LangGraph v2)      │  │
    │  │   ┌─────────┐  ┌─────────┐  ┌─────────┐  │  │
    │  │   │  LLM    │→ │  Tools  │→│ Checkptr │  │  │
    │  │   └─────────┘  └─────────┘  └─────────┘  │  │
    │  │   pre_model_hook: summarization          │  │
    │  └──────────────────────────────────────────┘  │
    │  + session analytics, token tracking           │
    └────────────────────────────────────────────────┘
"""

import logging
from typing import Any, Dict, List, Optional

from django.conf import settings
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.tools import tool as lc_tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.prebuilt import create_react_agent

from ..models import ChatSession
from .summarization_service import SummarizationService
from .tool_service import ToolService
from .vector_storage_service import VectorStorageService

logger = logging.getLogger(__name__)


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
# Checkpointer singleton
# ---------------------------------------------------------------------------

_checkpointer: Optional[PostgresSaver] = None


def get_checkpointer() -> PostgresSaver:
    """
    Return a ``PostgresSaver`` connected to ``settings.PG_CHECKPOINT_URI``.

    The first call creates the checkpoint tables (``.setup()``) and caches
    the instance for the lifetime of the process.
    """
    global _checkpointer
    if _checkpointer is None:
        _checkpointer = PostgresSaver.from_conn_string(settings.PG_CHECKPOINT_URI)
        _checkpointer.setup()
        logger.info("PostgresSaver checkpointer initialised")
    return _checkpointer


# ---------------------------------------------------------------------------
# ChatAgentOrchestrator — the main entry-point for agent interaction
# ---------------------------------------------------------------------------


class ChatAgentOrchestrator:
    """
    High-level orchestrator that owns a compiled ``create_react_agent``
    graph and provides ``invoke`` / ``stream`` methods.

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

        # LLM from session settings
        self.llm = ChatOpenAI(
            model=session.model_name,
            temperature=session.temperature,
        )

        # Tools
        self.tools = load_tools_for_user(self.user)

        # Checkpointer
        self.checkpointer = get_checkpointer()

        # Summarization hook (reads session + user preferences)
        self.pre_model_hook = SummarizationService.make_pre_model_hook(session)

        # System prompt
        self.system_prompt = system_prompt or self._build_system_prompt()

        # Build the compiled agent graph
        self.agent = create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=self.system_prompt,
            pre_model_hook=self.pre_model_hook,
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

        # Extract the last AI message as the response
        ai_response = ""
        for msg in reversed(result.get("messages", [])):
            if isinstance(msg, AIMessage):
                ai_response = msg.content
                break

        # Update session analytics
        msg_count = sum(1 for m in result.get("messages", []))
        self.session.update_analytics(message_count=2)  # human + assistant

        # Auto-title on first exchange
        if self.session.title == "New Conversation":
            self.session.update_title(user_message)

        return {
            "response": ai_response,
            "messages": result.get("messages", []),
            "session": self.session,
            "tokens_used": (
                getattr(result.get("messages", [None])[-1], "usage_metadata", {}).get(
                    "total_tokens", 0
                )
                if result.get("messages")
                else 0
            ),
        }

    # ------------------------------------------------------------------
    # Stream (async generator — for WebSocket / SSE)
    # ------------------------------------------------------------------

    def stream(self, user_message: str):
        """
        Yield LangGraph stream events for real-time output.

        Usage::

            for event in orchestrator.stream("Hello"):
                # event is a dict like {"agent": {"messages": [...]}}
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
        state = self.checkpointer.get_state(self.config)
        return state.values.get("messages", [])

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
