"""
Message Feedback model — user ratings and issue reports on AI responses.

This module defines :class:`MessageFeedback`, which captures thumbs-up/down
ratings, detailed text feedback, issue categories, and admin review state for
individual AI-generated messages.  It links to :class:`ChatSession` and
identifies the target message via LangGraph ``checkpoint_id`` +
``message_index`` (the ``unique_together`` constraint prevents duplicate
feedback per message per user).

Key design decisions
--------------------
- **``unique_together = ["checkpoint_id", "message_index", "user"]``** —
  one piece of feedback per message per user; attempting to create a
  duplicate raises ``IntegrityError``.
- **Admin review workflow** — ``reviewed``, ``reviewed_by``, ``action_taken``
  fields support a triage pipeline.  Use :meth:`mark_reviewed` and
  :meth:`escalate` to transition feedback through review states.
- **Sentiment helpers** — :attr:`is_positive`, :attr:`is_negative`,
  :attr:`sentiment_score` make it easy to aggregate feedback in analytics
  dashboards without hard-coding rating strings.
- **Class-method analytics** — :meth:`get_session_satisfaction`,
  :meth:`get_user_satisfaction`, :meth:`get_overall_satisfaction`, and
  :meth:`get_issue_breakdown` return ready-to-serialize dicts for admin
  dashboards.

Typical usage
-------------
::

    # Create feedback (thin viewset calls this)
    fb = MessageFeedback.create_feedback(
        user=request.user,
        chat_session=session,
        checkpoint_id=state["checkpoint_id"],
        message_index=msg_idx,
        rating="thumbs_up",
    )

    # Admin review
    fb.mark_reviewed(admin_user, action_taken="noted", admin_notes="Looks good")

    # Analytics
    stats = MessageFeedback.get_session_satisfaction(session)
    issues = MessageFeedback.get_issue_breakdown()

Models defined
--------------
- :class:`MessageFeedback` — per-message user feedback with admin review.
"""

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from core.models import TimestampedModel


class MessageFeedback(TimestampedModel):
    """
    Store user feedback on AI-generated messages.

    This helps with:
    - Quality monitoring
    - Model fine-tuning
    - User satisfaction tracking
    - Issue identification
    """

    # User and session
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="message_feedback",
        help_text=_("User who provided feedback"),
    )

    chat_session = models.ForeignKey(
        "chatbot.ChatSession",
        on_delete=models.CASCADE,
        related_name="message_feedback",
        help_text=_("Chat session this feedback belongs to"),
    )

    # Message identification from LangGraph checkpoint
    checkpoint_id = models.CharField(
        max_length=255, help_text=_("LangGraph checkpoint ID containing the message")
    )

    message_index = models.IntegerField(
        help_text=_("Index of the message in the checkpoint")
    )

    # Rating
    rating = models.CharField(
        max_length=20,
        choices=[
            ("thumbs_up", "Thumbs Up 👍"),
            ("thumbs_down", "Thumbs Down 👎"),
            ("excellent", "Excellent"),
            ("good", "Good"),
            ("neutral", "Neutral"),
            ("poor", "Poor"),
            ("very_poor", "Very Poor"),
        ],
        help_text=_("User rating for the message"),
    )

    # Feedback categories
    feedback_categories = models.JSONField(
        default=list,
        blank=True,
        help_text=_(
            'Categories of feedback (e.g., ["incorrect", "helpful", "creative"])'
        ),
    )

    # Text feedback
    feedback_text = models.TextField(
        blank=True, null=True, help_text=_("Optional detailed feedback from user")
    )

    # Issue tracking
    reported_issue = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        choices=[
            ("incorrect", "Incorrect Information"),
            ("harmful", "Harmful Content"),
            ("biased", "Biased Response"),
            ("off_topic", "Off Topic"),
            ("incomplete", "Incomplete Answer"),
            ("technical_error", "Technical Error"),
            ("other", "Other"),
        ],
        help_text=_("Type of issue if reporting a problem"),
    )

    # Context preservation
    message_preview = models.TextField(
        blank=True, null=True, help_text=_("Preview of the message (for admin review)")
    )

    model_used = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text=_("AI model that generated the message"),
    )

    # Admin review
    reviewed = models.BooleanField(
        default=False, help_text=_("Whether admin has reviewed this feedback")
    )

    reviewed_at = models.DateTimeField(
        null=True, blank=True, help_text=_("When this feedback was reviewed")
    )

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_feedback",
        help_text=_("Admin who reviewed this feedback"),
    )

    admin_notes = models.TextField(
        blank=True, null=True, help_text=_("Internal notes from admin review")
    )

    # Action taken
    action_taken = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        choices=[
            ("none", "No Action"),
            ("noted", "Noted for Training"),
            ("fixed", "Issue Fixed"),
            ("escalated", "Escalated"),
            ("user_notified", "User Notified"),
        ],
        help_text=_("Action taken based on this feedback"),
    )

    class Meta:
        verbose_name = _("Message Feedback")
        verbose_name_plural = _("Message Feedback")
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["user", "-created_at"], name="msgfeedback_user_date_idx"
            ),
            models.Index(
                fields=["chat_session", "-created_at"],
                name="msgfeedback_session_date_idx",
            ),
            models.Index(fields=["rating"], name="msgfeedback_rating_idx"),
            models.Index(fields=["reported_issue"], name="msgfeedback_issue_idx"),
            models.Index(fields=["reviewed"], name="msgfeedback_reviewed_idx"),
        ]
        unique_together = ["checkpoint_id", "message_index", "user"]

    def __str__(self):
        return f"{self.user.email} - {self.rating} - Session {self.chat_session.title}"

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_positive(self):
        """Check if this is positive feedback."""
        return self.rating in ["thumbs_up", "excellent", "good"]

    @property
    def is_negative(self):
        """Check if this is negative feedback."""
        return self.rating in ["thumbs_down", "poor", "very_poor"]

    @property
    def is_neutral(self):
        """Check if this is neutral feedback."""
        return self.rating == "neutral"

    @property
    def has_issue_report(self):
        """Check if a specific issue was reported."""
        return bool(self.reported_issue)

    @property
    def sentiment_score(self):
        """
        Return a numeric sentiment score (-1, 0, +1).

        Useful for aggregation in analytics dashboards.
        """
        if self.is_positive:
            return 1
        elif self.is_negative:
            return -1
        return 0

    # ------------------------------------------------------------------
    # Instance methods
    # ------------------------------------------------------------------

    def mark_reviewed(self, reviewer, action_taken="noted", admin_notes=""):
        """Mark feedback as reviewed by admin."""
        from django.utils import timezone

        self.reviewed = True
        self.reviewed_at = timezone.now()
        self.reviewed_by = reviewer
        self.action_taken = action_taken
        if admin_notes:
            self.admin_notes = admin_notes

        self.save(
            update_fields=[
                "reviewed",
                "reviewed_at",
                "reviewed_by",
                "action_taken",
                "admin_notes",
            ]
        )

    def escalate(self, escalated_by, reason=""):
        """
        Escalate feedback for urgent review.

        Args:
            escalated_by: Admin user who escalated
            reason: Escalation reason
        """
        from django.utils import timezone

        self.action_taken = "escalated"
        self.reviewed = True
        self.reviewed_at = timezone.now()
        self.reviewed_by = escalated_by
        if reason:
            self.admin_notes = f"[ESCALATED] {reason}"

        self.save(
            update_fields=[
                "action_taken",
                "reviewed",
                "reviewed_at",
                "reviewed_by",
                "admin_notes",
            ]
        )

    def to_display_dict(self):
        """
        Return a serializable dict for API responses.
        """
        return {
            "id": self.id,
            "rating": self.rating,
            "is_positive": self.is_positive,
            "sentiment_score": self.sentiment_score,
            "feedback_categories": self.feedback_categories,
            "feedback_text": self.feedback_text,
            "reported_issue": self.reported_issue,
            "model_used": self.model_used,
            "reviewed": self.reviewed,
            "action_taken": self.action_taken,
            "created_at": self.created_at.isoformat(),
        }

    # ------------------------------------------------------------------
    # Class methods — analytics
    # ------------------------------------------------------------------

    @classmethod
    def get_session_satisfaction(cls, chat_session):
        """
        Get satisfaction metrics for a session.

        Returns:
            dict: Satisfaction stats
        """
        feedback = cls.objects.filter(chat_session=chat_session)

        total = feedback.count()
        if total == 0:
            return {"total": 0, "satisfaction_rate": 0.0}

        positive = feedback.filter(
            rating__in=["thumbs_up", "excellent", "good"]
        ).count()
        negative = feedback.filter(
            rating__in=["thumbs_down", "poor", "very_poor"]
        ).count()

        return {
            "total": total,
            "positive": positive,
            "negative": negative,
            "neutral": total - positive - negative,
            "satisfaction_rate": (positive / total * 100) if total > 0 else 0.0,
        }

    @classmethod
    def get_user_satisfaction(cls, user):
        """Get overall satisfaction for user's conversations."""
        feedback = cls.objects.filter(user=user)

        total = feedback.count()
        if total == 0:
            return {"total": 0, "satisfaction_rate": 0.0}

        positive = feedback.filter(
            rating__in=["thumbs_up", "excellent", "good"]
        ).count()

        return {
            "total": total,
            "positive": positive,
            "satisfaction_rate": (positive / total * 100) if total > 0 else 0.0,
        }

    @classmethod
    def get_overall_satisfaction(cls):
        """
        Get platform-wide satisfaction metrics.

        Useful for admin dashboard / health metrics.

        Returns:
            dict with total, positive, negative, satisfaction_rate, avg_sentiment
        """
        from django.db.models import Count, Q

        aggregates = cls.objects.aggregate(
            total=Count("id"),
            positive=Count("id", filter=Q(rating__in=["thumbs_up", "excellent", "good"])),
            negative=Count("id", filter=Q(rating__in=["thumbs_down", "poor", "very_poor"])),
        )

        total = aggregates["total"]
        if total == 0:
            return {"total": 0, "satisfaction_rate": 0.0, "avg_sentiment": 0.0}

        return {
            "total": total,
            "positive": aggregates["positive"],
            "negative": aggregates["negative"],
            "neutral": total - aggregates["positive"] - aggregates["negative"],
            "satisfaction_rate": round(aggregates["positive"] / total * 100, 1),
        }

    @classmethod
    def get_unreviewed(cls, limit=None):
        """
        Get unreviewed feedback for admin review queue.

        Args:
            limit: Optional max results

        Returns:
            QuerySet of unreviewed feedback, newest first
        """
        qs = cls.objects.filter(reviewed=False).order_by("-created_at")
        if limit:
            qs = qs[:limit]
        return qs

    @classmethod
    def get_recent_feedback(cls, limit=10):
        """
        Get most recent feedback across all users (for admin dashboard).

        Args:
            limit: Max results to return

        Returns:
            QuerySet
        """
        return cls.objects.select_related("user", "chat_session").order_by(
            "-created_at"
        )[:limit]

    @classmethod
    def get_issue_breakdown(cls):
        """
        Get breakdown of reported issues by type.

        Returns:
            list of dicts: [{'reported_issue': str, 'count': int}]
        """
        return list(
            cls.objects.filter(reported_issue__isnull=False)
            .values("reported_issue")
            .annotate(count=models.Count("id"))
            .order_by("-count")
        )

    @classmethod
    def create_feedback(cls, user, chat_session, checkpoint_id, message_index,
                        rating, feedback_text=None, feedback_categories=None,
                        reported_issue=None, message_preview=None, model_used=None):
        """
        Create a feedback record with validation.

        Convenience method that handles the common creation pattern
        and prevents duplicate feedback (unique_together).

        Args:
            user: User providing feedback
            chat_session: ChatSession instance
            checkpoint_id: LangGraph checkpoint ID
            message_index: Message index in checkpoint
            rating: Rating choice value
            feedback_text: Optional text feedback
            feedback_categories: Optional list of category strings
            reported_issue: Optional issue type
            message_preview: Optional preview of the rated message
            model_used: Optional model name

        Returns:
            MessageFeedback instance

        Raises:
            IntegrityError: If feedback already exists for this message/user
        """
        return cls.objects.create(
            user=user,
            chat_session=chat_session,
            checkpoint_id=checkpoint_id,
            message_index=message_index,
            rating=rating,
            feedback_text=feedback_text or "",
            feedback_categories=feedback_categories or [],
            reported_issue=reported_issue,
            message_preview=message_preview,
            model_used=model_used,
        )
