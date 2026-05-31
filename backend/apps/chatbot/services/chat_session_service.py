"""
Chat Session Service

Handles all chat session operations including creation, retrieval, updates,
and analytics. Integrates with LangGraph's thread_id concept.

Usage:
    from chatbot.services import ChatSessionService

    # Create new session
    session = ChatSessionService.create_session(
        user=request.user,
        title="Python Help"
    )

    # Get user sessions
    sessions = ChatSessionService.get_user_sessions(user)

    # Update analytics
    ChatSessionService.update_session_analytics(
        session_id=session.id,
        message_count=1,
        tokens_used=150
    )
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from django.db.models import QuerySet, Q, Count, Sum
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from django.core.cache import cache

from ..models import ChatSession
from accounts.models import CustomUser


class ChatSessionService:
    """Service for managing chat sessions and threads."""

    @staticmethod
    def create_session(
        user: CustomUser,
        title: str = "New Conversation",
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        enable_summarization: Optional[bool] = None,
        custom_system_prompt: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ChatSession:
        """
        Create a new chat session.

        Args:
            user: The user creating the session
            title: Session title (default: "New Conversation")
            model_name: AI model to use (defaults to user preference)
            temperature: Model temperature (defaults to user preference)
            max_tokens: Max tokens (defaults to user preference)
            enable_summarization: Enable auto-summarization (defaults to user pref)
            custom_system_prompt: Custom system prompt (optional)
            metadata: Additional metadata (optional)

        Returns:
            Created ChatSession instance

        Example:
            session = ChatSessionService.create_session(
                user=request.user,
                title="Python Help",
                model_name="gpt-4o",
                temperature=0.7
            )
        """
        # Get user preferences for defaults
        user_prefs = user.ai_preferences

        session = ChatSession.objects.create(
            user=user,
            title=title,
            model_name=model_name or user_prefs.default_model,
            temperature=(
                temperature
                if temperature is not None
                else user_prefs.default_temperature
            ),
            max_tokens=max_tokens or user_prefs.default_max_tokens,
            enable_summarization=(
                enable_summarization
                if enable_summarization is not None
                else user_prefs.enable_auto_summarization
            ),
            custom_system_prompt=custom_system_prompt
            or user_prefs.custom_system_prompt,
            metadata=metadata or {},
        )

        return session

    @staticmethod
    def get_session(session_id: UUID, user: Optional[CustomUser] = None) -> ChatSession:
        """
        Get a chat session by ID.

        Args:
            session_id: Session UUID
            user: Optional user for permission check

        Returns:
            ChatSession instance

        Raises:
            ObjectDoesNotExist: If session not found or user mismatch

        Example:
            session = ChatSessionService.get_session(
                session_id=uuid.UUID("..."),
                user=request.user
            )
        """
        query = ChatSession.objects.filter(id=session_id)

        if user:
            query = query.filter(user=user)

        try:
            return query.select_related("user").get()
        except ChatSession.DoesNotExist:
            raise ObjectDoesNotExist(
                f"Chat session {session_id} not found or access denied"
            )

    @staticmethod
    def get_user_sessions(
        user: CustomUser,
        active_only: bool = True,
        archived: bool = False,
        limit: Optional[int] = None,
        search_query: Optional[str] = None,
    ) -> QuerySet:
        """
        Get all chat sessions for a user.

        Args:
            user: The user
            active_only: Only active sessions (default: True)
            archived: Include archived sessions (default: False)
            limit: Limit number of results (optional)
            search_query: Search in title and metadata (optional)

        Returns:
            QuerySet of ChatSession objects

        Example:
            sessions = ChatSessionService.get_user_sessions(
                user=request.user,
                active_only=True,
                limit=50
            )
        """
        query = ChatSession.objects.filter(user=user)

        if active_only:
            query = query.filter(is_active=True)

        if not archived:
            query = query.filter(is_archived=False)

        if search_query:
            query = query.filter(
                Q(title__icontains=search_query) | Q(metadata__icontains=search_query)
            )

        query = query.select_related("user").order_by("-updated_at")

        if limit:
            query = query[:limit]

        return query

    @staticmethod
    def update_session(session_id: UUID, user: CustomUser, **kwargs) -> ChatSession:
        """
        Update a chat session.

        Args:
            session_id: Session UUID
            user: User for permission check
            **kwargs: Fields to update (title, model_name, etc.)

        Returns:
            Updated ChatSession instance

        Example:
            session = ChatSessionService.update_session(
                session_id=session.id,
                user=request.user,
                title="Updated Title",
                is_pinned=True
            )
        """
        session = ChatSessionService.get_session(session_id, user)

        for field, value in kwargs.items():
            if hasattr(session, field):
                setattr(session, field, value)

        session.save()

        # Invalidate cache
        cache.delete(f"chat_session_{session_id}")

        return session

    @staticmethod
    def update_session_analytics(
        session_id: UUID,
        message_count: Optional[int] = None,
        tokens_used: Optional[int] = None,
        cost: Optional[float] = None,
    ) -> ChatSession:
        """
        Update session analytics (message count, tokens, cost).

        Args:
            session_id: Session UUID
            message_count: Increment message count by this amount
            tokens_used: Increment total tokens by this amount
            cost: Increment total cost by this amount

        Returns:
            Updated ChatSession instance

        Example:
            ChatSessionService.update_session_analytics(
                session_id=session.id,
                message_count=1,
                tokens_used=150,
                cost=0.002
            )
        """
        session = ChatSession.objects.get(id=session_id)

        if message_count:
            session.message_count += message_count

        if tokens_used:
            session.total_tokens_used += tokens_used

        if cost:
            session.total_cost += cost

        session.save(
            update_fields=[
                "message_count",
                "total_tokens_used",
                "total_cost",
                "updated_at",
            ]
        )

        return session

    @staticmethod
    def archive_session(session_id: UUID, user: CustomUser) -> ChatSession:
        """
        Archive a chat session.

        Args:
            session_id: Session UUID
            user: User for permission check

        Returns:
            Updated ChatSession instance

        Example:
            session = ChatSessionService.archive_session(
                session_id=session.id,
                user=request.user
            )
        """
        return ChatSessionService.update_session(
            session_id=session_id, user=user, is_archived=True, is_active=False
        )

    @staticmethod
    def delete_session(session_id: UUID, user: CustomUser) -> None:
        """
        Soft delete a chat session.

        Args:
            session_id: Session UUID
            user: User for permission check

        Example:
            ChatSessionService.delete_session(
                session_id=session.id,
                user=request.user
            )
        """
        session = ChatSessionService.get_session(session_id, user)
        session.is_active = False
        session.is_archived = True
        session.save()

        # Invalidate cache
        cache.delete(f"chat_session_{session_id}")

    @staticmethod
    def hard_delete_session(session_id: UUID, user: CustomUser) -> None:
        """
        Permanently delete a chat session.

        WARNING: This also deletes LangGraph checkpoints!

        Args:
            session_id: Session UUID
            user: User for permission check

        Example:
            ChatSessionService.hard_delete_session(
                session_id=session.id,
                user=request.user
            )
        """
        session = ChatSessionService.get_session(session_id, user)

        # TODO: Delete LangGraph checkpoints for this thread_id
        # This requires checkpointer service integration

        session.delete()

        # Invalidate cache
        cache.delete(f"chat_session_{session_id}")

    @staticmethod
    def get_session_statistics(session_id: UUID, user: CustomUser) -> Dict[str, Any]:
        """
        Get detailed statistics for a session.

        Args:
            session_id: Session UUID
            user: User for permission check

        Returns:
            Dictionary with statistics

        Example:
            stats = ChatSessionService.get_session_statistics(
                session_id=session.id,
                user=request.user
            )
        """
        session = ChatSessionService.get_session(session_id, user)

        # Get token usage stats
        token_stats = session.token_usage.aggregate(
            total_cost=Sum("total_cost"),
            total_tokens=Sum("total_tokens"),
            avg_response_time=Sum("response_time_ms") / Count("id"),
        )

        # Get feedback stats
        feedback_stats = session.message_feedback.aggregate(
            feedback_count=Count("id"),
            thumbs_up=Count("id", filter=Q(rating="thumbs_up")),
            thumbs_down=Count("id", filter=Q(rating="thumbs_down")),
        )

        return {
            "session_id": str(session.id),
            "title": session.title,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "message_count": session.message_count,
            "total_tokens": token_stats["total_tokens"] or 0,
            "total_cost": float(token_stats["total_cost"] or 0),
            "avg_response_time_ms": float(token_stats["avg_response_time"] or 0),
            "feedback_count": feedback_stats["feedback_count"],
            "satisfaction_rate": (
                (feedback_stats["thumbs_up"] / feedback_stats["feedback_count"] * 100)
                if feedback_stats["feedback_count"] > 0
                else 0
            ),
        }

    @staticmethod
    def get_user_statistics(user: CustomUser) -> Dict[str, Any]:
        """
        Get overall statistics for a user across all sessions.

        Args:
            user: The user

        Returns:
            Dictionary with user-level statistics

        Example:
            stats = ChatSessionService.get_user_statistics(
                user=request.user
            )
        """
        sessions = ChatSession.objects.filter(user=user)

        total_stats = sessions.aggregate(
            total_sessions=Count("id"),
            active_sessions=Count("id", filter=Q(is_active=True)),
            archived_sessions=Count("id", filter=Q(is_archived=True)),
            total_messages=Sum("message_count"),
            total_tokens=Sum("total_tokens_used"),
            total_cost=Sum("total_cost"),
        )

        return {
            "user_id": str(user.id),
            "total_sessions": total_stats["total_sessions"] or 0,
            "active_sessions": total_stats["active_sessions"] or 0,
            "archived_sessions": total_stats["archived_sessions"] or 0,
            "total_messages": total_stats["total_messages"] or 0,
            "total_tokens": total_stats["total_tokens"] or 0,
            "total_cost": float(total_stats["total_cost"] or 0),
        }

    @staticmethod
    def pin_session(session_id: UUID, user: CustomUser) -> ChatSession:
        """
        Pin a session to top of list.

        Args:
            session_id: Session UUID
            user: User for permission check

        Returns:
            Updated ChatSession instance
        """
        return ChatSessionService.update_session(
            session_id=session_id, user=user, is_pinned=True
        )

    @staticmethod
    def unpin_session(session_id: UUID, user: CustomUser) -> ChatSession:
        """
        Unpin a session.

        Args:
            session_id: Session UUID
            user: User for permission check

        Returns:
            Updated ChatSession instance
        """
        return ChatSessionService.update_session(
            session_id=session_id, user=user, is_pinned=False
        )

    @staticmethod
    def get_thread_config(session: ChatSession) -> Dict[str, Any]:
        """
        Get LangGraph configuration for this session.

        Args:
            session: ChatSession instance

        Returns:
            LangGraph config dict with thread_id and user settings

        Example:
            config = ChatSessionService.get_thread_config(session)
            response = agent.invoke({"messages": [msg]}, config)
        """
        return {
            "configurable": {
                "thread_id": str(session.id),
                "user_id": str(session.user.id),
                "model_name": session.model_name,
                "temperature": float(session.temperature),
                "max_tokens": session.max_tokens,
            }
        }
