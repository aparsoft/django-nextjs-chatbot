"""
Serializers for Chat Agent API.

These serializers handle request/response validation for the
chat agent endpoint — sending messages and receiving AI responses.

Unlike model-backed serializers, these are operation-based:
  - ChatAgentMessageSerializer  → validates incoming user messages
  - ChatAgentResponseSerializer  → formats the AI response
  - ChatAgentHistorySerializer   → formats conversation history items
"""

from rest_framework import serializers


# ---------------------------------------------------------------------------
#  Request Serializers
# ---------------------------------------------------------------------------


class ChatAgentMessageSerializer(serializers.Serializer):
    """Validate an incoming chat message from the user.

    Fields:
        message: The user's message text (required, 1–10 000 chars).
        system_prompt: Optional system prompt override.
    """

    message = serializers.CharField(
        min_length=1,
        max_length=10_000,
        help_text="The user's message to the AI agent.",
    )
    system_prompt = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=5_000,
        help_text="Optional system prompt override for this message.",
    )


# ---------------------------------------------------------------------------
#  Response Serializers
# ---------------------------------------------------------------------------


class ChatAgentResponseSerializer(serializers.Serializer):
    """Format the AI agent's response.

    Fields:
        response: The assistant's reply text.
        session_id: UUID of the chat session.
        tokens_used: Approximate tokens consumed.
        message_count: Total messages in the session after this turn.
    """

    response = serializers.CharField(help_text="The assistant's reply text.")
    session_id = serializers.UUIDField(help_text="UUID of the chat session.")
    tokens_used = serializers.IntegerField(
        help_text="Approximate tokens consumed in this turn.",
    )
    message_count = serializers.IntegerField(
        help_text="Total messages in the session after this turn.",
    )


class ChatAgentHistoryItemSerializer(serializers.Serializer):
    """A single message in the conversation history.

    Fields:
        role: One of 'human', 'ai', 'system', 'tool'.
        content: The message text (truncated for system/tool messages).
    """

    role = serializers.CharField()
    content = serializers.CharField()


class ChatAgentStreamChunkSerializer(serializers.Serializer):
    """A single streaming chunk from the agent.

    Fields:
        type: One of 'token', 'message', 'error', 'done'.
        content: The chunk text (empty for 'done' type).
    """

    type = serializers.ChoiceField(choices=["token", "message", "error", "done"])
    content = serializers.CharField(allow_blank=True)
