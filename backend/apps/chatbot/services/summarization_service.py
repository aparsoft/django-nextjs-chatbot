"""
Summarization Service

Handles automatic conversation summarization using LangGraph's SummarizationNode.
Implements October 2025 best practices for memory management.

Usage:
    from chatbot.services import SummarizationService

    # Create summarization node
    node = SummarizationService.create_summarization_node(
        model_name="gpt-4o-mini",
        max_tokens=384,
        max_summary_tokens=128
    )

    # Check if summarization needed
    if SummarizationService.should_summarize(messages):
        # Summarization will happen automatically via pre_model_hook
        pass
"""

from typing import List, Dict, Any, Optional, Callable
from uuid import UUID

from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.messages.utils import count_tokens_approximately
from langchain_openai import ChatOpenAI

from ..models import ChatSession


class SummarizationService:
    """Service for managing conversation summarization."""

    @staticmethod
    def create_summarization_node(
        model_name: str = "gpt-4o-mini",
        max_tokens: int = 384,
        max_summary_tokens: int = 128,
        token_counter: Optional[Callable] = None,
        output_messages_key: str = "llm_input_messages",
        summarization_prompt: Optional[str] = None,
    ) -> SummarizationNode:
        """
        Create a SummarizationNode for use with LangGraph agents.

        Args:
            model_name: Model to use for summarization (cheaper model recommended)
            max_tokens: Start summarizing when message history exceeds this
            max_summary_tokens: Maximum tokens in the summary
            token_counter: Custom token counting function (optional)
            output_messages_key: Key for summarized messages in state
            summarization_prompt: Custom summarization prompt (optional)

        Returns:
            Configured SummarizationNode instance

        Example:
            # Create summarization node
            summarization_node = SummarizationService.create_summarization_node(
                model_name="gpt-4o-mini",
                max_tokens=500,
                max_summary_tokens=150
            )

            # Use with ReAct agent
            from langgraph.prebuilt import create_react_agent

            agent = create_react_agent(
                model=ChatOpenAI(model="gpt-4o"),
                tools=[...],
                pre_model_hook=summarization_node,  # Auto-summarization!
                checkpointer=checkpointer
            )
        """
        model = ChatOpenAI(model=model_name, temperature=0)

        kwargs = {
            "token_counter": token_counter or count_tokens_approximately,
            "model": model,
            "max_tokens": max_tokens,
            "max_summary_tokens": max_summary_tokens,
            "output_messages_key": output_messages_key,
        }

        if summarization_prompt:
            kwargs["summarization_prompt"] = summarization_prompt

        return SummarizationNode(**kwargs)

    @staticmethod
    def should_summarize(
        messages: List[BaseMessage],
        threshold: int = 384,
        token_counter: Optional[Callable] = None,
    ) -> bool:
        """
        Check if conversation should be summarized.

        Args:
            messages: List of messages to check
            threshold: Token threshold for summarization
            token_counter: Custom token counting function

        Returns:
            True if summarization recommended

        Example:
            if SummarizationService.should_summarize(messages):
                print("Conversation will be summarized on next turn")
        """
        counter = token_counter or count_tokens_approximately
        token_count = counter(messages)
        return token_count > threshold

    @staticmethod
    def get_summarization_config(session: ChatSession) -> Dict[str, Any]:
        """
        Get summarization configuration from chat session settings.

        Args:
            session: ChatSession with summarization preferences

        Returns:
            Configuration dict for SummarizationNode

        Example:
            config = SummarizationService.get_summarization_config(session)
            node = SummarizationService.create_summarization_node(**config)
        """
        # Get user preferences
        user_prefs = session.user.ai_preferences

        config = {
            "model_name": "gpt-4o-mini",  # Use cheaper model for summarization
            "max_tokens": user_prefs.summarization_threshold or 384,
            "max_summary_tokens": user_prefs.max_summary_tokens or 128,
            "output_messages_key": "llm_input_messages",
        }

        return config

    @staticmethod
    def manual_summarize(
        messages: List[BaseMessage],
        model_name: str = "gpt-4o-mini",
        max_summary_tokens: int = 128,
        custom_prompt: Optional[str] = None,
    ) -> str:
        """
        Manually summarize a conversation (without SummarizationNode).

        Args:
            messages: Messages to summarize
            model_name: Model to use
            max_summary_tokens: Max tokens in summary
            custom_prompt: Custom summarization prompt

        Returns:
            Summary text

        Example:
            summary = SummarizationService.manual_summarize(
                messages=old_messages,
                max_summary_tokens=200
            )
        """
        model = ChatOpenAI(
            model=model_name, temperature=0, max_tokens=max_summary_tokens
        )

        # Build conversation text
        conversation_text = "\n".join(
            [f"{msg.type}: {msg.content}" for msg in messages]
        )

        # Default or custom prompt
        prompt = custom_prompt or (
            "Concisely summarize the key points of this conversation. "
            "Focus on important information and context:\n\n"
            f"{conversation_text}"
        )

        response = model.invoke([SystemMessage(content=prompt)])
        return response.content

    @staticmethod
    def create_summary_message(summary_text: str) -> SystemMessage:
        """
        Create a system message containing the summary.

        Args:
            summary_text: The summary text

        Returns:
            SystemMessage with summary

        Example:
            summary_msg = SummarizationService.create_summary_message(
                "Previous conversation covered Python basics and loops."
            )
            messages = [summary_msg] + recent_messages
        """
        return SystemMessage(
            content=f"Previous conversation summary: {summary_text}",
            additional_kwargs={"is_summary": True},
        )

    @staticmethod
    def summarize_and_compress(
        messages: List[BaseMessage],
        keep_recent: int = 10,
        model_name: str = "gpt-4o-mini",
    ) -> List[BaseMessage]:
        """
        Summarize older messages and keep recent ones in full.

        Args:
            messages: All messages
            keep_recent: Number of recent messages to keep in full
            model_name: Model for summarization

        Returns:
            Compressed message list with summary + recent messages

        Example:
            compressed = SummarizationService.summarize_and_compress(
                messages=all_messages,
                keep_recent=10
            )
        """
        if len(messages) <= keep_recent:
            return messages

        # Split into old and recent
        old_messages = messages[:-keep_recent]
        recent_messages = messages[-keep_recent:]

        # Summarize old messages
        summary = SummarizationService.manual_summarize(
            messages=old_messages, model_name=model_name
        )

        # Create summary message
        summary_msg = SummarizationService.create_summary_message(summary)

        # Combine summary + recent
        return [summary_msg] + recent_messages

    @staticmethod
    def get_token_count(
        messages: List[BaseMessage], counter: Optional[Callable] = None
    ) -> int:
        """
        Count tokens in message list.

        Args:
            messages: Messages to count
            counter: Custom token counter (optional)

        Returns:
            Total token count

        Example:
            tokens = SummarizationService.get_token_count(messages)
            print(f"Conversation uses {tokens} tokens")
        """
        counter = counter or count_tokens_approximately
        return counter(messages)

    @staticmethod
    def estimate_summary_savings(
        messages: List[BaseMessage],
        keep_recent: int = 10,
        max_summary_tokens: int = 128,
    ) -> Dict[str, int]:
        """
        Estimate token savings from summarization.

        Args:
            messages: Messages to analyze
            keep_recent: How many recent to keep
            max_summary_tokens: Expected summary size

        Returns:
            Dict with original, compressed, and saved tokens

        Example:
            savings = SummarizationService.estimate_summary_savings(messages)
            print(f"Would save {savings['saved_tokens']} tokens")
        """
        original_tokens = SummarizationService.get_token_count(messages)

        if len(messages) <= keep_recent:
            return {
                "original_tokens": original_tokens,
                "compressed_tokens": original_tokens,
                "saved_tokens": 0,
                "savings_percent": 0.0,
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
            "saved_tokens": saved_tokens,
            "savings_percent": round(savings_percent, 2),
        }

    @staticmethod
    def update_session_summarization_settings(
        session_id: UUID,
        enable: bool,
        threshold: Optional[int] = None,
        max_summary_tokens: Optional[int] = None,
    ) -> ChatSession:
        """
        Update summarization settings for a session.

        Args:
            session_id: Chat session ID
            enable: Enable/disable summarization
            threshold: Token threshold (optional)
            max_summary_tokens: Max summary size (optional)

        Returns:
            Updated ChatSession

        Example:
            session = SummarizationService.update_session_summarization_settings(
                session_id=session.id,
                enable=True,
                threshold=500
            )
        """
        session = ChatSession.objects.get(id=session_id)
        session.enable_summarization = enable

        if threshold:
            # Store in user preferences
            prefs = session.user.ai_preferences
            prefs.summarization_threshold = threshold
            if max_summary_tokens:
                prefs.max_summary_tokens = max_summary_tokens
            prefs.save()

        session.save()
        return session
