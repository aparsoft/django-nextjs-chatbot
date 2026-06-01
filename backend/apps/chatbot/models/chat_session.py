"""
Chat Session Model - Maps to LangGraph threads with user-facing metadata.

This model doesn't store messages (LangGraph checkpointer does that).
It stores user-friendly metadata about conversations like titles and settings.
"""

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from core.models import TimestampedModel
import uuid


class ChatSession(TimestampedModel):
    """
    Chat session metadata that maps to LangGraph thread_id.

    The actual conversation state (messages, checkpoints) is stored in
    PG_CHECKPOINT_URI by LangGraph's PostgresCheckpointer.

    This model stores user-facing metadata like titles and descriptions.
    """

    # Primary identification
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text=_("UUID that also serves as LangGraph thread_id"),
    )

    # User association
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_sessions",
        help_text=_("User who owns this chat session"),
    )

    # User-friendly metadata
    title = models.CharField(
        max_length=255,
        default="New Conversation",
        help_text=_("User-defined or auto-generated conversation title"),
    )

    description = models.TextField(
        blank=True,
        null=True,
        help_text=_("Optional description or summary of the conversation"),
    )

    # Session configuration
    model_name = models.CharField(
        max_length=100,
        default="gpt-5-mini",
        help_text=_("AI model used for this session"),
    )

    temperature = models.FloatField(
        default=0.7, help_text=_("Model temperature (0.0 to 2.0)")
    )

    # Session settings
    enable_summarization = models.BooleanField(
        default=True, help_text=_("Enable automatic conversation summarization")
    )

    summarization_threshold = models.IntegerField(
        default=384, help_text=_("Token count to trigger summarization")
    )

    # Status and visibility
    is_active = models.BooleanField(
        default=True, help_text=_("Whether this session is active")
    )

    is_archived = models.BooleanField(
        default=False, help_text=_("Whether this session is archived")
    )

    is_pinned = models.BooleanField(
        default=False, help_text=_("Whether this session is pinned to top")
    )

    # Additional metadata
    tags = models.JSONField(
        default=list, blank=True, help_text=_("User-defined tags for organization")
    )

    metadata = models.JSONField(
        default=dict, blank=True, help_text=_("Additional session metadata")
    )

    # Analytics
    message_count = models.IntegerField(
        default=0, help_text=_("Total messages in this session (updated via signals)")
    )

    total_tokens_used = models.IntegerField(
        default=0, help_text=_("Total tokens used in this session")
    )

    last_message_at = models.DateTimeField(
        null=True, blank=True, help_text=_("Timestamp of last message in this session")
    )

    class Meta:
        verbose_name = _("Chat Session")
        verbose_name_plural = _("Chat Sessions")
        ordering = ["-is_pinned", "-last_message_at", "-updated_at"]
        indexes = [
            models.Index(
                fields=["user", "-last_message_at"], name="chatsession_user_lastmsg_idx"
            ),
            models.Index(
                fields=["user", "is_active"], name="chatsession_user_active_idx"
            ),
            models.Index(
                fields=["user", "is_archived"], name="chatsession_user_archived_idx"
            ),
            models.Index(
                fields=["is_pinned", "-last_message_at"], name="chatsession_pinned_idx"
            ),
        ]

    def __str__(self):
        return f"{self.title} ({self.user.email})"

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def thread_id(self):
        """Return the UUID as string for use with LangGraph."""
        return str(self.id)

    @property
    def is_new(self):
        """Check if this session has no messages yet."""
        return self.message_count == 0

    @property
    def title_preview(self):
        """Truncated title for sidebar / list views (max 50 chars)."""
        if len(self.title) <= 50:
            return self.title
        return self.title[:47] + "..."

    # ------------------------------------------------------------------
    # Instance methods — state transitions & analytics
    # ------------------------------------------------------------------

    def get_langgraph_config(self):
        """
        Return the config dict needed by LangGraph's agent.invoke().

        Usage in viewset:
            config = session.get_langgraph_config()
            response = agent.invoke({"messages": [msg]}, config)
        """
        return {
            "configurable": {
                "thread_id": self.thread_id,
            }
        }

    def update_analytics(self, message_count=None, tokens_used=None, save=True):
        """
        Update session analytics after a message exchange.

        Args:
            message_count: Messages to add (typically 2: user + assistant)
            tokens_used: Tokens consumed in this exchange
            save: Whether to save immediately (set False if caller will save)
        """
        from django.utils import timezone

        if message_count is not None:
            self.message_count += message_count

        if tokens_used is not None:
            self.total_tokens_used += tokens_used

        self.last_message_at = timezone.now()

        if save:
            self.save(
                update_fields=["message_count", "total_tokens_used", "last_message_at"]
            )

    def archive(self):
        """Archive this session (inactive + archived)."""
        self.is_archived = True
        self.is_active = False
        self.save(update_fields=["is_archived", "is_active"])

    def activate(self):
        """Reactivate an archived session."""
        self.is_archived = False
        self.is_active = True
        self.save(update_fields=["is_archived", "is_active"])

    def toggle_pin(self):
        """Toggle pin status."""
        self.is_pinned = not self.is_pinned
        self.save(update_fields=["is_pinned"])

    def soft_delete(self):
        """
        Soft-delete: archive + deactivate + clear sensitive metadata.

        The session record stays in DB for analytics, but won't appear
        in user-facing lists. This is the pattern interns should learn
        instead of hard deletes for user data.
        """
        self.is_active = False
        self.is_archived = True
        self.metadata = {}
        self.tags = []
        self.save(update_fields=["is_active", "is_archived", "metadata", "tags"])

    def update_title(self, first_message, max_length=50):
        """
        Auto-generate a session title from the first user message.

        Called after the first message is sent so the sidebar shows
        something meaningful instead of "New Conversation".
        """
        if self.title != "New Conversation":
            return  # Already has a custom title

        title = first_message.strip().replace("\n", " ")
        if len(title) > max_length:
            title = title[: max_length - 3] + "..."
        self.title = title
        self.save(update_fields=["title"])

    def get_analytics_summary(self):
        """
        Return a dict of analytics for this session.

        Combines session-level counters with aggregate data from
        TokenUsage and MessageFeedback.
        """
        from decimal import Decimal

        summary = {
            "session_id": self.thread_id,
            "title": self.title,
            "message_count": self.message_count,
            "total_tokens": self.total_tokens_used,
            "created_at": self.created_at.isoformat(),
            "last_message_at": (
                self.last_message_at.isoformat() if self.last_message_at else None
            ),
            "is_active": self.is_active,
            "is_archived": self.is_archived,
        }

        # Token cost from TokenUsage aggregate
        cost = self.token_usage.aggregate(total=models.Sum("total_cost"))["total"]
        summary["total_cost"] = float(cost) if cost else 0.0

        return summary

    # ------------------------------------------------------------------
    # Class methods — queryset helpers (thin viewsets call these)
    # ------------------------------------------------------------------

    @classmethod
    def get_active_for_user(cls, user):
        """Get all active sessions for a user, newest first."""
        return cls.objects.filter(
            user=user, is_active=True, is_archived=False
        ).order_by("-is_pinned", "-last_message_at")

    @classmethod
    def get_archived_for_user(cls, user):
        """Get all archived sessions for a user."""
        return cls.objects.filter(user=user, is_archived=True).order_by("-updated_at")

    @classmethod
    def get_pinned_for_user(cls, user):
        """Get pinned sessions for a user."""
        return cls.objects.filter(
            user=user, is_pinned=True, is_active=True
        ).order_by("-last_message_at")

    @classmethod
    def get_session_stats(cls, user):
        """
        Aggregate session statistics for a user.

        Returns:
            dict with total_sessions, active_count, archived_count,
            total_messages, total_tokens
        """
        from django.db.models import Count, Sum

        stats = cls.objects.filter(user=user).aggregate(
            total_sessions=Count("id"),
            active_count=Count("id", filter=models.Q(is_active=True)),
            archived_count=Count("id", filter=models.Q(is_archived=True)),
            total_messages=Sum("message_count"),
            total_tokens=Sum("total_tokens_used"),
        )

        stats["total_messages"] = stats["total_messages"] or 0
        stats["total_tokens"] = stats["total_tokens"] or 0

        return stats

    @classmethod
    def create_for_user(cls, user, preferences=None, **kwargs):
        """
        Create a new session, pulling defaults from UserPreference.

        Args:
            user: The user
            preferences: UserPreference instance (fetched automatically if None)
            **kwargs: Override any field (title, model_name, etc.)

        Returns:
            ChatSession instance
        """
        if preferences is None:
            try:
                preferences = user.ai_preferences
            except Exception:
                preferences = None

        if preferences:
            defaults = preferences.get_session_config()
            # Only keep keys that are actual ChatSession model fields
            valid_fields = {f.name for f in cls._meta.get_fields()}
            defaults = {k: v for k, v in defaults.items() if k in valid_fields}
        else:
            defaults = {}

        # User-provided kwargs override preference defaults
        defaults.update(kwargs)
        defaults["user"] = user

        return cls.objects.create(**defaults)

    @classmethod
    def cleanup_old_sessions(cls, days_inactive=90):
        """
        Archive sessions with no activity for N days.

        Returns:
            int: Number of sessions archived
        """
        from django.utils import timezone
        from datetime import timedelta

        cutoff = timezone.now() - timedelta(days=days_inactive)

        stale = cls.objects.filter(
            is_active=True,
            is_archived=False,
            last_message_at__lt=cutoff,
        )
        count = stale.count()
        stale.update(is_active=False, is_archived=True)

        return count
