"""
API Key Service

Handles encrypted API key management for users.

Usage:
    from chatbot.services import APIKeyService

    # Store user's API key
    api_key = APIKeyService.create_api_key(
        user=user,
        provider="openai",
        api_key="sk-...",
        key_name="My OpenAI Key"
    )
"""

from typing import Optional, List, Dict, Any
from uuid import UUID

from ..models import UserAPIKey
from accounts.models import CustomUser


class APIKeyService:
    """Service for managing user API keys."""

    @staticmethod
    def create_api_key(
        user: CustomUser,
        provider: str,
        api_key: str,
        key_name: Optional[str] = None,
        is_default: bool = False,
    ) -> UserAPIKey:
        """
        Create and encrypt user API key.

        Args:
            user: The user
            provider: Provider name (openai, anthropic, etc.)
            api_key: The actual API key (will be encrypted)
            key_name: User-friendly name
            is_default: Set as default key for provider

        Returns:
            Created UserAPIKey instance

        Example:
            api_key = APIKeyService.create_api_key(
                user=request.user,
                provider="openai",
                api_key="sk-proj-...",
                key_name="My OpenAI Key",
                is_default=True
            )
        """
        # If setting as default, unset other defaults
        if is_default:
            UserAPIKey.objects.filter(
                user=user, provider=provider, is_default=True
            ).update(is_default=False)

        # Create key
        user_api_key = UserAPIKey.objects.create(
            user=user,
            provider=provider,
            key_name=key_name or f"{provider.title()} Key",
            is_default=is_default,
        )

        # Encrypt and save
        user_api_key.encrypt_api_key(api_key)
        user_api_key.save()

        return user_api_key

    @staticmethod
    def get_user_keys(
        user: CustomUser, provider: Optional[str] = None
    ) -> List[UserAPIKey]:
        """
        Get user's API keys.

        Args:
            user: The user
            provider: Filter by provider (optional)

        Returns:
            List of UserAPIKey instances
        """
        query = UserAPIKey.objects.filter(user=user, is_active=True)

        if provider:
            query = query.filter(provider=provider)

        return list(query.order_by("-is_default", "-created_at"))

    @staticmethod
    def get_default_key(user: CustomUser, provider: str) -> Optional[UserAPIKey]:
        """
        Get user's default key for a provider.

        Args:
            user: The user
            provider: Provider name

        Returns:
            UserAPIKey instance or None
        """
        try:
            return UserAPIKey.objects.get(
                user=user, provider=provider, is_default=True, is_active=True
            )
        except UserAPIKey.DoesNotExist:
            # Try to get any active key
            try:
                return UserAPIKey.objects.filter(
                    user=user, provider=provider, is_active=True
                ).first()
            except:
                return None

    @staticmethod
    def get_decrypted_key(user: CustomUser, provider: str) -> Optional[str]:
        """
        Get decrypted API key for provider.

        Args:
            user: The user
            provider: Provider name

        Returns:
            Decrypted API key or None

        Example:
            api_key = APIKeyService.get_decrypted_key(
                user=request.user,
                provider="openai"
            )

            if api_key:
                # Use key with OpenAI
                client = OpenAI(api_key=api_key)
        """
        user_api_key = APIKeyService.get_default_key(user, provider)

        if user_api_key:
            return user_api_key.decrypt_api_key()

        return None

    @staticmethod
    def validate_key(user: CustomUser, key_id: UUID) -> Dict[str, Any]:
        """
        Validate an API key.

        Args:
            user: The user
            key_id: UserAPIKey ID

        Returns:
            Validation result dict
        """
        user_api_key = UserAPIKey.objects.get(id=key_id, user=user)
        result = user_api_key.validate_key()

        if result["valid"]:
            user_api_key.is_validated = True
            user_api_key.save()

        return result

    @staticmethod
    def delete_key(user: CustomUser, key_id: UUID) -> None:
        """
        Delete an API key.

        Args:
            user: The user
            key_id: UserAPIKey ID
        """
        UserAPIKey.objects.filter(id=key_id, user=user).delete()

    @staticmethod
    def set_default_key(user: CustomUser, key_id: UUID) -> UserAPIKey:
        """
        Set a key as default for its provider.

        Args:
            user: The user
            key_id: UserAPIKey ID

        Returns:
            Updated UserAPIKey instance
        """
        user_api_key = UserAPIKey.objects.get(id=key_id, user=user)

        # Unset other defaults
        UserAPIKey.objects.filter(
            user=user, provider=user_api_key.provider, is_default=True
        ).update(is_default=False)

        # Set as default
        user_api_key.is_default = True
        user_api_key.save()

        return user_api_key
