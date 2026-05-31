"""
Message Service

Handles message operations with LangGraph PostgresCheckpointer integration.
Manages conversation history, retrieval, and state management.

Usage:
    from chatbot.services import MessageService

    # Get conversation history
    messages = MessageService.get_conversation_history(
        thread_id=session.id
    )

    # Add user message
    MessageService.add_message(
        thread_id=session.id,
        content="Hello!",
        message_type="human"
    )
"""

from typing import List, Dict, Any, Optional
from uuid import UUID
from django.conf import settings

from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    SystemMessage,
    ToolMessage,
    BaseMessage,
)
from langgraph.checkpoint.postgres import PostgresSaver

from ..models import ChatSession


class MessageService:
    """Service for managing messages via LangGraph checkpointer."""

    @staticmethod
    def _get_checkpointer() -> PostgresSaver:
        """
        Get PostgresSaver instance for checkpointing.

        Returns:
            PostgresSaver instance connected to PG_CHECKPOINT_URI
        """
        checkpointer = PostgresSaver.from_conn_string(settings.PG_CHECKPOINT_URI)
        # Ensure tables exist
        checkpointer.setup()
        return checkpointer

    @staticmethod
    def get_conversation_history(
        thread_id: UUID,
        limit: Optional[int] = None,
        checkpoint_id: Optional[str] = None,
    ) -> List[BaseMessage]:
        """
        Get conversation history from LangGraph checkpointer.

        Args:
            thread_id: Chat session ID (also LangGraph thread_id)
            limit: Limit number of messages (optional)
            checkpoint_id: Specific checkpoint to retrieve (optional)

        Returns:
            List of LangChain message objects

        Example:
            messages = MessageService.get_conversation_history(
                thread_id=session.id,
                limit=50
            )
        """
        checkpointer = MessageService._get_checkpointer()

        # Build config
        config = {"configurable": {"thread_id": str(thread_id)}}

        if checkpoint_id:
            config["configurable"]["checkpoint_id"] = checkpoint_id

        # Get state from checkpointer
        try:
            state = checkpointer.get_state(config)
            messages = state.get("messages", [])

            if limit:
                messages = messages[-limit:]

            return messages
        except Exception as e:
            # If thread doesn't exist yet, return empty list
            return []

    @staticmethod
    def get_state_history(
        thread_id: UUID, limit: Optional[int] = 10
    ) -> List[Dict[str, Any]]:
        """
        Get checkpoint history for a thread.

        Args:
            thread_id: Chat session ID
            limit: Number of checkpoints to retrieve

        Returns:
            List of checkpoint state snapshots

        Example:
            history = MessageService.get_state_history(
                thread_id=session.id,
                limit=5
            )
        """
        checkpointer = MessageService._get_checkpointer()

        config = {"configurable": {"thread_id": str(thread_id)}}

        history = []
        for state in checkpointer.list(config, limit=limit):
            history.append(
                {
                    "checkpoint_id": state.config["configurable"].get("checkpoint_id"),
                    "timestamp": state.metadata.get("created_at"),
                    "message_count": len(state.values.get("messages", [])),
                    "metadata": state.metadata,
                }
            )

        return history

    @staticmethod
    def add_message(
        thread_id: UUID,
        content: str,
        message_type: str = "human",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> BaseMessage:
        """
        Add a message to the conversation.

        Note: This is typically done automatically by the agent.
        Use this for manual message addition.

        Args:
            thread_id: Chat session ID
            content: Message content
            message_type: Type of message (human, ai, system, tool)
            metadata: Additional metadata

        Returns:
            Created message object

        Example:
            msg = MessageService.add_message(
                thread_id=session.id,
                content="Hello!",
                message_type="human"
            )
        """
        # Create appropriate message type
        message_classes = {
            "human": HumanMessage,
            "ai": AIMessage,
            "system": SystemMessage,
            "tool": ToolMessage,
        }

        MessageClass = message_classes.get(message_type, HumanMessage)

        message = MessageClass(content=content, additional_kwargs=metadata or {})

        return message

    @staticmethod
    def get_message_at_checkpoint(
        thread_id: UUID, checkpoint_id: str
    ) -> List[BaseMessage]:
        """
        Get messages at a specific checkpoint (time-travel).

        Args:
            thread_id: Chat session ID
            checkpoint_id: Specific checkpoint ID

        Returns:
            List of messages at that checkpoint

        Example:
            messages = MessageService.get_message_at_checkpoint(
                thread_id=session.id,
                checkpoint_id="1ef663ba-28fe-6528-8002-5a559208592c"
            )
        """
        return MessageService.get_conversation_history(
            thread_id=thread_id, checkpoint_id=checkpoint_id
        )

    @staticmethod
    def update_state(
        thread_id: UUID, values: Dict[str, Any], as_node: Optional[str] = None
    ) -> None:
        """
        Update conversation state (advanced usage).

        Args:
            thread_id: Chat session ID
            values: State values to update
            as_node: Update as if from this node

        Example:
            MessageService.update_state(
                thread_id=session.id,
                values={"custom_key": "custom_value"},
                as_node="agent"
            )
        """
        checkpointer = MessageService._get_checkpointer()

        config = {"configurable": {"thread_id": str(thread_id)}}

        checkpointer.update_state(config=config, values=values, as_node=as_node)

    @staticmethod
    def format_messages_for_display(
        messages: List[BaseMessage],
    ) -> List[Dict[str, Any]]:
        """
        Format LangChain messages for API response.

        Args:
            messages: List of LangChain message objects

        Returns:
            List of message dictionaries for frontend

        Example:
            messages = MessageService.get_conversation_history(thread_id)
            formatted = MessageService.format_messages_for_display(messages)
        """
        formatted = []

        for msg in messages:
            formatted_msg = {
                "role": msg.type,
                "content": msg.content,
                "id": getattr(msg, "id", None),
                "timestamp": msg.additional_kwargs.get("timestamp"),
                "metadata": msg.additional_kwargs,
            }

            # Add tool calls if present
            if hasattr(msg, "tool_calls"):
                formatted_msg["tool_calls"] = msg.tool_calls

            # Add tool call ID if present
            if hasattr(msg, "tool_call_id"):
                formatted_msg["tool_call_id"] = msg.tool_call_id

            formatted.append(formatted_msg)

        return formatted

    @staticmethod
    def delete_thread_history(thread_id: UUID) -> None:
        """
        Delete all checkpoints for a thread.

        WARNING: This permanently deletes conversation history!

        Args:
            thread_id: Chat session ID to delete

        Example:
            MessageService.delete_thread_history(thread_id=session.id)
        """
        checkpointer = MessageService._get_checkpointer()

        config = {"configurable": {"thread_id": str(thread_id)}}

        # Delete all checkpoints for this thread
        checkpointer.delete_state(config)

    @staticmethod
    def get_latest_checkpoint_id(thread_id: UUID) -> Optional[str]:
        """
        Get the latest checkpoint ID for a thread.

        Args:
            thread_id: Chat session ID

        Returns:
            Latest checkpoint ID or None

        Example:
            checkpoint_id = MessageService.get_latest_checkpoint_id(
                thread_id=session.id
            )
        """
        checkpointer = MessageService._get_checkpointer()

        config = {"configurable": {"thread_id": str(thread_id)}}

        try:
            state = checkpointer.get_state(config)
            return state.config["configurable"].get("checkpoint_id")
        except:
            return None

    @staticmethod
    def count_messages(thread_id: UUID) -> int:
        """
        Count messages in a thread.

        Args:
            thread_id: Chat session ID

        Returns:
            Number of messages

        Example:
            count = MessageService.count_messages(thread_id=session.id)
        """
        messages = MessageService.get_conversation_history(thread_id)
        return len(messages)

    @staticmethod
    def get_last_n_messages(thread_id: UUID, n: int = 10) -> List[BaseMessage]:
        """
        Get last N messages from conversation.

        Args:
            thread_id: Chat session ID
            n: Number of recent messages

        Returns:
            List of last N messages

        Example:
            recent_msgs = MessageService.get_last_n_messages(
                thread_id=session.id,
                n=5
            )
        """
        return MessageService.get_conversation_history(thread_id=thread_id, limit=n)

    @staticmethod
    def search_messages(thread_id: UUID, search_query: str) -> List[Dict[str, Any]]:
        """
        Search messages in a conversation.

        Args:
            thread_id: Chat session ID
            search_query: Text to search for

        Returns:
            List of matching messages with context

        Example:
            results = MessageService.search_messages(
                thread_id=session.id,
                search_query="python"
            )
        """
        messages = MessageService.get_conversation_history(thread_id)

        results = []
        for i, msg in enumerate(messages):
            if search_query.lower() in msg.content.lower():
                results.append(
                    {
                        "index": i,
                        "role": msg.type,
                        "content": msg.content,
                        "match_preview": msg.content[:200],
                    }
                )

        return results
