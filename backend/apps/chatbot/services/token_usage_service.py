"""
Token Usage Service

Handles token tracking, cost calculation, and usage analytics.

Usage:
    from chatbot.services import TokenUsageService

    # Track token usage
    usage = TokenUsageService.track_usage(
        user=user,
        session=session,
        model_name="gpt-4o",
        prompt_tokens=150,
        completion_tokens=75
    )
"""

from typing import Dict, Any, Optional
from uuid import UUID
from decimal import Decimal

from django.db.models import Sum, Avg, Count, Q
from django.utils import timezone
from datetime import datetime, timedelta

from ..models import TokenUsage, ChatSession
from accounts.models import CustomUser


class TokenUsageService:
    """Service for tracking and analyzing token usage."""

    # Pricing per 1M tokens (October 2025)
    MODEL_PRICING = {
        "gpt-4o": {
            "prompt": Decimal("2.50"),  # $2.50 per 1M prompt tokens
            "completion": Decimal("10.00"),  # $10.00 per 1M completion tokens
        },
        "gpt-4o-mini": {
            "prompt": Decimal("0.15"),  # $0.15 per 1M prompt tokens
            "completion": Decimal("0.60"),  # $0.60 per 1M completion tokens
        },
        "gpt-3.5-turbo": {"prompt": Decimal("0.50"), "completion": Decimal("1.50")},
    }

    @staticmethod
    def calculate_cost(
        model_name: str, prompt_tokens: int, completion_tokens: int
    ) -> Dict[str, Decimal]:
        """
        Calculate cost for token usage.

        Args:
            model_name: AI model name
            prompt_tokens: Input tokens
            completion_tokens: Output tokens

        Returns:
            Dict with prompt_cost, completion_cost, total_cost

        Example:
            costs = TokenUsageService.calculate_cost(
                model_name="gpt-4o",
                prompt_tokens=150,
                completion_tokens=75
            )
        """
        pricing = TokenUsageService.MODEL_PRICING.get(
            model_name, TokenUsageService.MODEL_PRICING["gpt-4o"]  # Default
        )

        # Calculate costs (pricing is per 1M tokens)
        prompt_cost = (Decimal(prompt_tokens) / Decimal(1000000)) * pricing["prompt"]
        completion_cost = (Decimal(completion_tokens) / Decimal(1000000)) * pricing[
            "completion"
        ]

        return {
            "prompt_cost": prompt_cost,
            "completion_cost": completion_cost,
            "total_cost": prompt_cost + completion_cost,
        }

    @staticmethod
    def track_usage(
        user: CustomUser,
        session: ChatSession,
        model_name: str,
        prompt_tokens: int,
        completion_tokens: int,
        request_type: str = "chat",
        response_time_ms: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TokenUsage:
        """
        Track token usage for a request.

        Args:
            user: User making the request
            session: Chat session
            model_name: AI model used
            prompt_tokens: Input tokens
            completion_tokens: Output tokens
            request_type: Type of request (chat, summarization, etc.)
            response_time_ms: Response time in milliseconds
            metadata: Additional metadata

        Returns:
            Created TokenUsage instance

        Example:
            usage = TokenUsageService.track_usage(
                user=request.user,
                session=session,
                model_name="gpt-4o",
                prompt_tokens=150,
                completion_tokens=75,
                response_time_ms=1200
            )
        """
        # Calculate costs
        costs = TokenUsageService.calculate_cost(
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

        # Create usage record
        usage = TokenUsage.objects.create(
            user=user,
            chat_session=session,
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            prompt_cost=costs["prompt_cost"],
            completion_cost=costs["completion_cost"],
            total_cost=costs["total_cost"],
            request_type=request_type,
            response_time_ms=response_time_ms,
            metadata=metadata or {},
        )

        # Update session analytics
        session.total_tokens_used += usage.total_tokens
        session.total_cost += usage.total_cost
        session.save(update_fields=["total_tokens_used", "total_cost", "updated_at"])

        return usage

    @staticmethod
    def check_user_limits(
        user: CustomUser, additional_tokens: int = 0
    ) -> Dict[str, Any]:
        """
        Check if user has exceeded usage limits.

        Args:
            user: The user
            additional_tokens: Tokens about to be used

        Returns:
            Dict with allowed status and reason

        Example:
            limit_check = TokenUsageService.check_user_limits(
                user=request.user,
                additional_tokens=200
            )

            if not limit_check['allowed']:
                return Response({'error': limit_check['reason']}, status=429)
        """
        prefs = user.ai_preferences

        # Get today's usage
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_usage = TokenUsage.objects.filter(
            user=user, created_at__gte=today_start
        ).aggregate(total_tokens=Sum("total_tokens"), total_cost=Sum("total_cost"))

        current_tokens = today_usage["total_tokens"] or 0
        current_cost = float(today_usage["total_cost"] or 0)

        # Check token limit
        if prefs.daily_token_limit:
            if current_tokens + additional_tokens > prefs.daily_token_limit:
                return {
                    "allowed": False,
                    "reason": f"Daily token limit exceeded ({prefs.daily_token_limit})",
                    "current_usage": current_tokens,
                    "limit": prefs.daily_token_limit,
                }

        # Check cost limit
        if prefs.daily_cost_limit:
            # Estimate cost of additional tokens (use gpt-4o pricing as worst case)
            estimated_cost = TokenUsageService.calculate_cost(
                "gpt-4o", additional_tokens, 0
            )["prompt_cost"]

            if current_cost + float(estimated_cost) > prefs.daily_cost_limit:
                return {
                    "allowed": False,
                    "reason": f"Daily cost limit exceeded (${prefs.daily_cost_limit})",
                    "current_cost": current_cost,
                    "limit": float(prefs.daily_cost_limit),
                }

        return {
            "allowed": True,
            "current_tokens": current_tokens,
            "current_cost": current_cost,
        }

    @staticmethod
    def get_user_usage_stats(user: CustomUser, days: int = 30) -> Dict[str, Any]:
        """
        Get usage statistics for a user.

        Args:
            user: The user
            days: Number of days to analyze

        Returns:
            Dict with usage statistics

        Example:
            stats = TokenUsageService.get_user_usage_stats(
                user=request.user,
                days=30
            )
        """
        cutoff_date = timezone.now() - timedelta(days=days)

        usage = TokenUsage.objects.filter(user=user, created_at__gte=cutoff_date)

        stats = usage.aggregate(
            total_requests=Count("id"),
            total_tokens=Sum("total_tokens"),
            total_cost=Sum("total_cost"),
            avg_tokens_per_request=Avg("total_tokens"),
            avg_response_time=Avg("response_time_ms"),
        )

        # Group by model
        by_model = (
            usage.values("model_name")
            .annotate(
                requests=Count("id"), tokens=Sum("total_tokens"), cost=Sum("total_cost")
            )
            .order_by("-cost")
        )

        return {
            "period_days": days,
            "total_requests": stats["total_requests"] or 0,
            "total_tokens": stats["total_tokens"] or 0,
            "total_cost": float(stats["total_cost"] or 0),
            "avg_tokens_per_request": float(stats["avg_tokens_per_request"] or 0),
            "avg_response_time_ms": float(stats["avg_response_time"] or 0),
            "usage_by_model": list(by_model),
        }

    @staticmethod
    def get_daily_usage(
        user: CustomUser, date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get usage for a specific day.

        Args:
            user: The user
            date: Specific date (defaults to today)

        Returns:
            Dict with daily usage
        """
        target_date = date or timezone.now()
        day_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        usage = TokenUsage.objects.filter(
            user=user, created_at__gte=day_start, created_at__lt=day_end
        )

        stats = usage.aggregate(
            total_requests=Count("id"),
            total_tokens=Sum("total_tokens"),
            total_cost=Sum("total_cost"),
        )

        return {
            "date": day_start.date(),
            "total_requests": stats["total_requests"] or 0,
            "total_tokens": stats["total_tokens"] or 0,
            "total_cost": float(stats["total_cost"] or 0),
        }
