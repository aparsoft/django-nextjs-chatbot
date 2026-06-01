"""
Action-based ViewSet for the Chat Agent API.

Provides REST endpoints for interacting with the LangGraph agent.
This is the primary API the Next.js frontend uses to send messages
and receive AI responses.

Custom actions (auto-routed by DefaultRouter):
    ┌────────┬────────────────────────────────────────────────┬──────────────┐
    │ Method │ URL                                            │ Action       │
    ├────────┼────────────────────────────────────────────────┼──────────────┤
    │ POST   │ /chat-agent/send/                              │ send         │
    │ GET    │ /chat-agent/history/{session_id}/              │ history      │
    │ GET    │ /chat-agent/sessions/                          │ sessions     │
    └────────┴────────────────────────────────────────────────┴──────────────┘

Business logic lives in AgentService — the viewset only handles
HTTP concerns (request parsing, response formatting, status codes).
"""

import logging

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view

from core.permissions import IsOwnerOrAdmin

from ...models import ChatSession
from ...services import AgentService

from ..serializers import (
    ChatAgentMessageSerializer,
    ChatAgentResponseSerializer,
    ChatAgentHistoryItemSerializer,
    ChatSessionListSerializer,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  ChatAgent ViewSet
# ---------------------------------------------------------------------------


@extend_schema_view(
    send=extend_schema(
        tags=["Chat Agent"],
        summary="Send a message to the AI agent",
        description=(
            "Send a user message to the LangGraph agent and receive "
            "an AI response. Creates a new session if no session_id "
            "is provided."
        ),
        request=ChatAgentMessageSerializer,
        responses={200: ChatAgentResponseSerializer},
    ),
    history=extend_schema(
        tags=["Chat Agent"],
        summary="Get conversation history",
        description="Retrieve the conversation history for a session.",
        responses={200: ChatAgentHistoryItemSerializer(many=True)},
    ),
    sessions=extend_schema(
        tags=["Chat Agent"],
        summary="List user's active sessions",
        description="Return the authenticated user's active chat sessions.",
        responses={200: ChatSessionListSerializer(many=True)},
    ),
)
@extend_schema(tags=["Chat Agent"])
class ChatAgentViewSet(viewsets.ViewSet):
    """
    API endpoints for the LangGraph chat agent.

    This ViewSet is **not** model-backed — it delegates all business
    logic to ``AgentService`` and ``ChatSession`` model methods.
    """

    permission_classes = [IsOwnerOrAdmin]

    # ------------------------------------------------------------------
    # POST /chat-agent/send/
    # ------------------------------------------------------------------

    @action(detail=False, methods=["post"], url_path="send")
    def send(self, request):
        """
        Send a message to the AI agent and receive a response.

        Request body:
            message (str, required): The user's message (1–10 000 chars).
            session_id (str, optional): UUID of an existing session.
            system_prompt (str, optional): Override the system prompt.

        If no session_id is provided, a new session is created using
        the user's default preferences.
        """
        serializer = ChatAgentMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        message = serializer.validated_data["message"]
        system_prompt = serializer.validated_data.get("system_prompt") or None

        # Resolve or create session
        session_id = request.data.get("session_id")
        if session_id:
            try:
                session = ChatSession.objects.get(
                    id=session_id,
                    user=user,
                    is_active=True,
                )
            except ChatSession.DoesNotExist:
                return Response(
                    {"detail": "Session not found or inactive."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            from ...models import UserPreference

            prefs, _ = UserPreference.objects.get_or_create(user=user)
            session = ChatSession.create_for_user(user, preferences=prefs)

        # Invoke the agent
        try:
            result = AgentService.chat(
                session=session,
                user_message=message,
                system_prompt=system_prompt,
            )
        except Exception as exc:
            logger.exception("Agent error for user %s: %s", user.email, exc)
            return Response(
                {"detail": f"Agent error: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            ChatAgentResponseSerializer(
                {
                    "response": result["response"],
                    "session_id": session.id,
                    "tokens_used": result.get("tokens_used", 0),
                    "message_count": session.message_count,
                }
            ).data
        )

    # ------------------------------------------------------------------
    # GET /chat-agent/history/{session_id}/
    # ------------------------------------------------------------------

    @action(
        detail=False,
        methods=["get"],
        url_path="history/(?P<session_id>[0-9a-f-]+)",
    )
    def history(self, request, session_id=None):
        """
        Get conversation history for a session.

        Returns a list of messages in chronological order.
        """
        try:
            session = ChatSession.objects.get(
                id=session_id,
                user=request.user,
            )
        except ChatSession.DoesNotExist:
            return Response(
                {"detail": "Session not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            orchestrator = AgentService.create_orchestrator(session)
            messages = orchestrator.get_history_display()
        except Exception:
            # Fallback: return empty history if checkpointer has no state yet
            messages = []

        serializer = ChatAgentHistoryItemSerializer(messages, many=True)
        return Response(serializer.data)

    # ------------------------------------------------------------------
    # GET /chat-agent/sessions/
    # ------------------------------------------------------------------

    @action(detail=False, methods=["get"], url_path="sessions")
    def sessions(self, request):
        """
        List the authenticated user's active chat sessions.

        Returns lightweight session data for the sidebar / session list.
        """
        sessions = ChatSession.get_active_for_user(request.user)
        serializer = ChatSessionListSerializer(sessions, many=True)
        return Response(serializer.data)
