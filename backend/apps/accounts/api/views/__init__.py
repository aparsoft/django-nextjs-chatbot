# accounts/api/views/__init__.py

"""
ViewSets package for accounts API.
"""

# Auth views
from .auth_views import (
    CustomTokenObtainPairView,
    LogoutView,
)

# Auth register views
from .auth_register_views import (
    RegisterView,
    OrganizationRegisterView,
    CSRFTokenView,
)

# Auth password reset views
from .auth_password_reset_views import (
    PasswordResetView,
    PasswordResetConfirmView,
    EmailVerificationView,
    PasswordChangeView,
)

# CustomUser viewsets
from .custom_user_views import (
    CustomUserViewSet,
    UserContactViewSet,
)

# Profile avatar views
from .profile_avatar_views import (
    ProfileAvatarView,
)

__all__ = [
    # Auth
    "CustomTokenObtainPairView",
    "LogoutView",
    # Registration
    "RegisterView",
    "OrganizationRegisterView",
    "CSRFTokenView",
    # Password management
    "PasswordResetView",
    "PasswordResetConfirmView",
    "PasswordChangeView",
    "EmailVerificationView",
    # User management
    "CustomUserViewSet",
    "UserContactViewSet",
    # Profile
    "ProfileAvatarView",
]
