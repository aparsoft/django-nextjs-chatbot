"""
Summarization Service

Handles automatic conversation summarization using LangGraph's PostgresSaver
for checkpointing and ChatOpenAI for generating summaries.

This service does NOT depend on langmem (not installed). Instead it implements
summarization as a LangGraph node that can be inserted into any agent graph
or called standalone.

How it works:
    1. Count tokens in the conversation history (via checkpointer)
    2. When tokens exceed a threshold, summarize older messages
    3. Replace old messages with a single SystemMessage summary
    4. Keep recent N messages intact for continuity
    5. Store the compressed state back via checkpointer

Usage:
    # Standalone — summarize a session's history
    from chatbot.services import SummarizationService

    result = SummarizationService.summarize_session(session)
    print(f"Saved {result['tokens_saved']} tokens")

    # As a LangGraph node — add to your graph
    graph.add_node("summarize", SummarizationService.make_graph_node())
    graph.add_edge("agent", "summarize")

    # With create_react_agent — use as pre_model_hook
    from langgraph.prebuilt import create_react_agent

    agent = create_react_agent(
        model=ChatOpenAI(model="gpt-4o-mini"),
        tools=my_tools,
        pre_model_hook=SummarizationService.make_pre_model_hook(session),
        checkpointer=checkpointer,
    )
"""

import logging
from typing import List, Dict, Any, Optional, Callable
from uuid import UUID

from django.conf import settings
from langchain_core.messages import (
    BaseMessage,
    SystemMessage,
    HumanMessage,
    AIMessage,
)
from langchain_core.messages.utils import count_tokens_approximately
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres import PostgresSaver

from ..models import ChatSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Default prompts — can be overridden per session/style
# ---------------------------------------------------------------------------

DEFAULT_SUMMARY_PROMPT = (
    "You are a conversation summarizer. Given a conversation history, "
    "produce a concise summary that preserves:\n"
    "1. Key decisions and conclusions reached\n"
    "2. Important facts, names, dates, and numbers mentioned\n"
    "3. Open questions or unresolved topics\n"
    "4. The user's goal or intent\n\n"
    "Be concise but complete. Write in third person."
)

BULLET_SUMMARY_PROMPT = (
    "You are a conversation summarizer. Given a conversation history, "
    "produce a bullet-point summary that captures:\n"
    "- Key decisions and conclusions\n"
    "- Important facts, names, dates, numbers\n"
    "- Open questions\n"
    "- User's goal or intent\n\n"
    "Use clear, short bullet points."
)

DETAILED_SUMMARY_PROMPT = (
    "You are a conversation summarizer. Given a conversation history, "
    "produce a detailed summary organized into sections:\n\n"
    "## Topics Discussed\n"
    "(list each topic)\n\n"
    "## Key Decisions\n"
    "(decisions made)\n\n"
    "## Important Facts\n"
    "(facts, names, dates, numbers)\n\n"
    "## Open Questions\n"
    "(unresolved items)\n\n"
    "## User Intent\n"
    "(what the user is trying to accomplish)"
)

STYLE_PROMPTS = {
    "concise": DEFAULT_SUMMARY_PROMPT,
    "bullet": BULLET_SUMMARY_PROMPT,
    "detailed": DETAILED_SUMMARY_PROMPT,
}


class SummarizationService:
    """Service for managing conversation summarization with LangGraph."""

    # ------------------------------------------------------------------
    # Checkpointer access (shared with MessageService)
    # ------------------------------------------------------------------

    @staticmethod
    def _get_checkpointer() -> PostgresSaver:
        """
        Get PostgresSaver connected to the langchain_history database.

        Returns:
            PostgresSaver instance (tables created if needed)
        """
        checkpointer = PostgresSaver.from_conn_string(settings.PG_CHECKPOINT_URI)
        checkpointer.setup()
        return checkpointer

    # ------------------------------------------------------------------
    # Token counting
    # ------------------------------------------------------------------

    @staticmethod
    def get_token_count(
        messages: List[BaseMessage],
        counter: Optional[Callable] = None,
    ) -> int:
        """
        Count approximate tokens in a message list.

        Args:
            messages: Messages to count
            counter: Custom counter function (defaults to approximate)

        Returns:
            Total token count
        """
        _counter = counter or count_tokens_approximately
        return _counter(messages)

    @staticmethod
    def should_summarize(
        messages: List[BaseMessage],
        threshold: int = 384,
        counter: Optional[Callable] = None,
    ) -> bool:
        """
        Check if conversation history exceeds the summarization threshold.

        Args:
            messages: Current conversation messages
            threshold: Token count that triggers summarization
            counter: Custom token counter

        Returns:
            True if summarization is recommended
        """
        return SummarizationService.get_token_count(messages, counter) > threshold

    # ------------------------------------------------------------------
    # Core summarization — generate summary from messages
    # ------------------------------------------------------------------

    @staticmethod
    def _get_style_prompt(style: str) -> str:
        """Get the summarization prompt for a given style."""
        return STYLE_PROMPTS.get(style, DEFAULT_SUMMARY_PROMPT)

    @staticmethod
    def generate_summary(
        messages: List[BaseMessage],
        model_name: str = "gpt-4o-mini",
        max_summary_tokens: int = 128,
        custom_prompt: Optional[str] = None,
        style: str = "concise",
    ) -> str:
        """
        Generate a text summary from a list of messages.

        Args:
            messages: Messages to summarize
            model_name: LLM model (cheaper model recommended)
            max_summary_tokens: Max tokens in output summary
            custom_prompt: Override the system prompt entirely
            style: One of "concise", "bullet", "detailed"

        Returns:
            Summary text
        """
        if not messages:
            return ""

        model = ChatOpenAI(
            model=model_name,
            temperature=0,
            max_tokens=max_summary_tokens,
        )

        # Build conversation text from messages
        conversation_lines = []
        for msg in messages:
            role = msg.type.upper()
            content = msg.content
            if isinstance(content, list):
                # Handle multi-modal content (text + images)
                content = " ".join(
                    part.get("text", "") for part in content
                    if isinstance(part, dict) and part.get("type") == "text"
                )
            conversation_lines.append(f"{role}: {content}")

        conversation_text = "\n".join(conversation_lines)

        system_prompt = custom_prompt or SummarizationService._get_style_prompt(style)

        response = model.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Conversation to summarize:\n\n{conversation_text}"),
        ])

        return response.content

    @staticmethod
    def create_summary_message(summary_text: str) -> SystemMessage:
        """
        Wrap a summary string into a SystemMessage for injection into
        the conversation.

        Args:
            summary_text: The summary content

        Returns:
            SystemMessage tagged with is_summary metadata
        """
        return SystemMessage(
            content=f"[Conversation Summary]\n{summary_text}",
            additional_kwargs={"is_summary": True, "type": "summarization"},
        )

    # ------------------------------------------------------------------
    # Compress — summary + keep recent messages
    # ------------------------------------------------------------------

    @staticmethod
    def compress_messages(
        messages: List[BaseMessage],
        keep_recent: int = 10,
        model_name: str = "gpt-4o-mini",
        max_summary_tokens: int = 128,
        style: str = "concise",
    ) -> List[BaseMessage]:
        """
        Compress message history: summarize older messages, keep recent ones.

        This is the core compression algorithm:
            1. If total messages ≤ keep_recent, return as-is
            2. Split into old_messages and recent_messages
            3. Summarize old_messages via LLM
            4. Return [summary_message] + recent_messages

        Args:
            messages: Full message history
            keep_recent: Number of recent messages to preserve
            model_name: Model for summarization
            max_summary_tokens: Max tokens in summary
            style: Summary style ("concise", "bullet", "detailed")

        Returns:
            Compressed message list
        """
        if len(messages) <= keep_recent:
            return messages

        old_messages = messages[:-keep_recent]
        recent_messages = messages[-keep_recent:]

        # Skip SystemMessages at the start — they're usually the original
        # system prompt, not conversation content
        system_prefix = []
        conversation_messages = old_messages
        if old_messages and isinstance(old_messages[0], SystemMessage):
            # Check if it's a previous summary — if so, include in summarization
            is_prev_summary = old_messages[0].additional_kwargs.get("is_summary", False)
            if not is_prev_summary:
                system_prefix = [old_messages[0]]
                conversation_messages = old_messages[1:]

        if not conversation_messages:
            return messages

        logger.info(
            "Summarizing %d old messages (keeping %d recent, style=%s)",
            len(conversation_messages),
            keep_recent,
            style,
        )

        summary_text = SummarizationService.generate_summary(
            messages=conversation_messages,
            model_name=model_name,
            max_summary_tokens=max_summary_tokens,
            style=style,
        )

        summary_msg = SummarizationService.create_summary_message(summary_text)

        compressed = system_prefix + [summary_msg] + recent_messages

        logger.info(
            "Compressed %d messages → %d (%d tokens saved)",
            len(messages),
            len(compressed),
            SummarizationService.get_token_count(messages)
            - SummarizationService.get_token_count(compressed),
        )

        return compressed

    # ------------------------------------------------------------------
    # Estimate savings (for UI display)
    # ------------------------------------------------------------------

    @staticmethod
    def estimate_savings(
        messages: List[BaseMessage],
        keep_recent: int = 10,
        max_summary_tokens: int = 128,
    ) -> Dict[str, Any]:
        """
        Estimate token savings from summarization (no API call).

        Args:
            messages: Current messages
            keep_recent: How many to keep
            max_summary_tokens: Expected summary size

        Returns:
            Dict with original, compressed, saved tokens and percent
        """
        original_tokens = SummarizationService.get_token_count(messages)

        if len(messages) <= keep_recent:
            return {
                "original_tokens": original_tokens,
                "compressed_tokens": original_tokens,
                "saved_tokens": 0,
                "savings_percent": 0.0,
                "would_summarize": False,
            }

        recent_tokens = SummarizationService.get_token_count(messages[-keep_recent:])
        compressed_tokens = max_summary_tokens + recent_tokens
        saved_tokens = original_tokens - compressed_tokens
        savings_percent = (
            (saved_tokens / original_tokens * 100) if original_tokens > 0 else 0
        )

        return {
            "original_tokens": original_tokens,
            "compressed_tokens": compressed_tokens,
            "saved_tokens": max(0, saved_tokens),
            "savings_percent": round(savings_percent, 2),
            "would_summarize": True,
        }

    # ------------------------------------------------------------------
    # Session-level summarization (reads preferences from ChatSession)
    # ------------------------------------------------------------------

    @staticmethod
    def get_session_config(session: ChatSession) -> Dict[str, Any]:
        """
        Get summarization config from session + user preferences.

        Reads:
            - session.enable_summarization
            - session.summarization_threshold
            - user preferences for style and max_summary_tokens

        Args:
            session: ChatSession instance

        Returns:
            Config dict for summarization methods
        """
        try:
            prefs = session.user.ai_preferences
            threshold = session.summarization_threshold or prefs.summarization_trigger_tokens
            max_summary = prefs.max_summary_tokens or 128
            style = prefs.summarization_style or "concise"
        except Exception:
            threshold = session.summarization_threshold or 384
            max_summary = 128
            style = "concise"

        return {
            "enabled": session.enable_summarization,
            "threshold": threshold,
            "max_summary_tokens": max_summary,
            "style": style,
            "model_name": "gpt-4o-mini",
            "keep_recent": 10,
        }

    @staticmethod
    def summarize_session(session: ChatSession) -> Dict[str, Any]:
        """
        Summarize a session's conversation history end-to-end.

        Reads the session's messages from the PostgresSaver checkpointer,
        compresses them if they exceed the threshold, and updates the
        checkpoint state.

        Args:
            session: ChatSession instance

        Returns:
            Dict with summary result (tokens saved, summary text, etc.)
        """
        config = SummarizationService.get_session_config(session)

        if not config["enabled"]:
            return {
                "summarized": False,
                "reason": "Summarization disabled for this session",
            }

        checkpointer = SummarizationService._get_checkpointer()
        thread_config = session.get_langgraph_config()

        # Get current state
        try:
            state = checkpointer.get_state(thread_config)
            messages = state.values.get("messages", [])
        except Exception:
            return {
                "summarized": False,
                "reason": "No conversation history found",
            }

        if not messages:
            return {"summarized": False, "reason": "No messages to summarize"}

        # Check threshold
        token_count = SummarizationService.get_token_count(messages)
        if token_count <= config["threshold"]:
            return {
                "summarized": False,
                "reason": f"Below threshold ({token_count} <= {config['threshold']})",
                "token_count": token_count,
            }

        # Compress
        original_tokens = token_count
        compressed = SummarizationService.compress_messages(
            messages=messages,
            keep_recent=config["keep_recent"],
            model_name=config["model_name"],
            max_summary_tokens=config["max_summary_tokens"],
            style=config["style"],
        )

        new_tokens = SummarizationService.get_token_count(compressed)

        # Update the checkpointer state with compressed messages
        checkpointer.update_state(
            config=thread_config,
            values={"messages": compressed},
            as_node="summarization",
        )

        # Update session analytics
        saved = original_tokens - new_tokens
        session.update_analytics(tokens_used=-saved)  # Negative = tokens saved

        # Extract summary text for the result
        summary_text = ""
        for msg in compressed:
            if isinstance(msg, SystemMessage) and msg.additional_kwargs.get("is_summary"):
                summary_text = msg.content.replace("[Conversation Summary]\n", "")
                break

        logger.info(
            "Session %s summarized: %d → %d tokens (saved %d)",
            session.id,
            original_tokens,
            new_tokens,
            saved,
        )

        return {
            "summarized": True,
            "original_tokens": original_tokens,
            "new_tokens": new_tokens,
            "tokens_saved": saved,
            "message_count_before": len(messages),
            "message_count_after": len(compressed),
            "summary_text": summary_text,
        }

    # ------------------------------------------------------------------
    # LangGraph integration — use as a node or pre_model_hook
    # ------------------------------------------------------------------

    @staticmethod
    def make_graph_node(
        model_name: str = "gpt-4o-mini",
        threshold: int = 384,
        keep_recent: int = 10,
        max_summary_tokens: int = 128,
        style: str = "concise",
    ) -> Callable:
        """
        Create a LangGraph node function for summarization.

        Use this when building a custom LangGraph graph:

            from langgraph.graph import StateGraph, MessagesState

            graph = StateGraph(MessagesState)
            graph.add_node("agent", agent_node)
            graph.add_node("summarize", SummarizationService.make_graph_node())
            graph.add_edge("agent", "summarize")

        The node reads messages from state, compresses if needed,
        and returns the updated messages.

        Args:
            model_name: LLM for summarization
            threshold: Token threshold to trigger compression
            keep_recent: Messages to keep intact
            max_summary_tokens: Max summary size
            style: Summary style

        Returns:
            Callable node function for LangGraph
        """

        def summarization_node(state: Dict[str, Any]) -> Dict[str, Any]:
            """LangGraph node that compresses message history."""
            messages = state.get("messages", [])

            if not SummarizationService.should_summarize(messages, threshold):
                return state  # No change needed

            compressed = SummarizationService.compress_messages(
                messages=messages,
                keep_recent=keep_recent,
                model_name=model_name,
                max_summary_tokens=max_summary_tokens,
                style=style,
            )

            return {"messages": compressed}

        return summarization_node

    @staticmethod
    def make_pre_model_hook(
        session: ChatSession,
    ) -> Callable:
        """
        Create a pre_model_hook for create_react_agent.

        This runs BEFORE each LLM call — if the conversation is getting
        long, it compresses the history so the LLM sees a summary instead
        of the full history.

        Usage:
            from langgraph.prebuilt import create_react_agent

            agent = create_react_agent(
                model=ChatOpenAI(model="gpt-4o-mini"),
                tools=my_tools,
                pre_model_hook=SummarizationService.make_pre_model_hook(session),
                checkpointer=checkpointer,
            )

        Args:
            session: ChatSession to read preferences from

        Returns:
            Callable pre_model_hook function
        """
        config = SummarizationService.get_session_config(session)

        def pre_model_hook(state: Dict[str, Any]) -> Dict[str, Any]:
            """Compress messages before sending to LLM."""
            if not config["enabled"]:
                return state

            messages = state.get("messages", [])

            if not SummarizationService.should_summarize(messages, config["threshold"]):
                return state

            compressed = SummarizationService.compress_messages(
                messages=messages,
                keep_recent=config["keep_recent"],
                model_name=config["model_name"],
                max_summary_tokens=config["max_summary_tokens"],
                style=config["style"],
            )

            return {"messages": compressed}

        return pre_model_hook

    # ------------------------------------------------------------------
    # Session settings update
    # ------------------------------------------------------------------

    @staticmethod
    def update_session_settings(
        session_id: UUID,
        enable: Optional[bool] = None,
        threshold: Optional[int] = None,
    ) -> ChatSession:
        """
        Update summarization settings for a chat session.

        Args:
            session_id: ChatSession UUID
            enable: Enable/disable summarization
            threshold: New token threshold

        Returns:
            Updated ChatSession
        """
        session = ChatSession.objects.get(id=session_id)

        if enable is not None:
            session.enable_summarization = enable

        if threshold is not None:
            session.summarization_threshold = threshold

        session.save()
        return session
