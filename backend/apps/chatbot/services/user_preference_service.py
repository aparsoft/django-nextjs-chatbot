"""
User Preference Service

Handles user AI preferences and settings management.

Usage:
    from chatbot.services import UserPreferenceService

    # Get or create preferences
    prefs = UserPreferenceService.get_or_create_preferences(user)

    # Update preferences
    UserPreferenceService.update_preferences(
        user=user,
        default_model="gpt-4o",
        enable_auto_summarization=True
    )
"""

from typing import Dict, Any, Optional

from ..models import UserPreference
from accounts.models import CustomUser


class UserPreferenceService:
    """Service for managing user preferences."""

    @staticmethod
    def get_or_create_preferences(user: CustomUser) -> UserPreference:
        """
        Get or create user preferences.

        Args:
            user: The user

        Returns:
            UserPreference instance
        """
        prefs, created = UserPreference.objects.get_or_create(user=user)
        return prefs

    @staticmethod
    def update_preferences(user: CustomUser, **kwargs) -> UserPreference:
        """
        Update user preferences.

        Args:
            user: The user
            **kwargs: Fields to update

        Returns:
            Updated UserPreference instance

        Example:
            prefs = UserPreferenceService.update_preferences(
                user=request.user,
                default_model="gpt-4o",
                default_temperature=0.8,
                enable_auto_summarization=True
            )
        """
        prefs = UserPreferenceService.get_or_create_preferences(user)

        for field, value in kwargs.items():
            if hasattr(prefs, field):
                setattr(prefs, field, value)

        prefs.save()
        return prefs

    @staticmethod
    def get_session_config(user: CustomUser) -> Dict[str, Any]:
        """
        Get session configuration from user preferences.

        Args:
            user: The user

        Returns:
            Config dict for creating ChatSession
        """
        prefs = UserPreferenceService.get_or_create_preferences(user)
        return prefs.get_session_config()

    @staticmethod
    def reset_to_defaults(user: CustomUser) -> UserPreference:
        """
        Reset preferences to defaults.

        Args:
            user: The user

        Returns:
            Reset UserPreference instance
        """
        prefs = UserPreferenceService.get_or_create_preferences(user)

        prefs.default_model = "gpt-4o-mini"
        prefs.default_temperature = 0.7
        prefs.default_max_tokens = 2048
        prefs.enable_auto_summarization = True
        prefs.custom_system_prompt = ""
        prefs.save()

        return prefs
