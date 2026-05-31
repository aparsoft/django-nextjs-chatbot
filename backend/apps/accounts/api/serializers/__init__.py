"""
Serializers package for accounts API.
"""

from .auth_serializers import (
    CustomTokenObtainPairSerializer,
    CustomTokenRefreshSerializer,
    RegisterSerializer,
    SocialAuthSerializer,
    PasswordChangeSerializer,
)

# CustomUser serializers
from .custom_user_serializers import (
    CustomUserSerializer,
    CustomUserListSerializer,
    CustomUserCreateSerializer,
    CustomUserUpdateSerializer,
    UserContactSerializer,
    UserContactCreateSerializer,
    UserContactUpdateSerializer,
)

__all__ = [
    # Auth serializers
    "CustomTokenObtainPairSerializer",
    "CustomTokenRefreshSerializer",
    "RegisterSerializer",
    "SocialAuthSerializer",
    "PasswordChangeSerializer",
    # CustomUser serializers
    "CustomUserSerializer",
    "CustomUserListSerializer",
    "CustomUserCreateSerializer",
    "CustomUserUpdateSerializer",
    # UserContact serializers
    "UserContactSerializer",
    "UserContactCreateSerializer",
    "UserContactUpdateSerializer",
]
