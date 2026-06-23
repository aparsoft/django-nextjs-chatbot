# accounts/api/urls.py

"""
URL configuration for accounts API.
Provides router-based URL patterns for all viewsets in the accounts app.
"""

from django.urls import path, include
from rest_framework_simplejwt.views import TokenVerifyView
from rest_framework.routers import DefaultRouter

from .views import (
    # Auth views
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
    LogoutView,
    RegisterView,
    CSRFTokenView,
    EmailVerificationView,
    PasswordResetView,
    PasswordResetConfirmView,
    PasswordChangeView,
    OrganizationRegisterView,
    # Social / OAuth views
    GoogleLoginView,
    # CustomUser viewsets
    CustomUserViewSet,
    UserContactViewSet,
    # Profile
    ProfileAvatarView,
)

app_name = "accounts"

# Initialize the default router
router = DefaultRouter()

# Register CustomUser viewsets
router.register(r"users", CustomUserViewSet, basename="user")
router.register(r"user-contacts", UserContactViewSet, basename="user-contact")

# URL patterns
urlpatterns = [
    # Router generated URLs
    path("", include(router.urls)),
    # Authentication endpoints
    path("auth/login/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/refresh/", CustomTokenRefreshView.as_view(), name="token_refresh"),
    path("auth/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("auth/logout/", LogoutView.as_view(), name="auth_logout"),
    path("auth/register/", RegisterView.as_view(), name="auth_register"),
    path(
        "auth/social/google/",
        GoogleLoginView.as_view(),
        name="auth_social_google",
    ),
    path(
        "auth/organization-register/",
        OrganizationRegisterView.as_view(),
        name="auth_organization_register",
    ),
    # Password management
    path(
        "auth/password/reset/",
        PasswordResetView.as_view(),
        name="auth_password_reset",
    ),
    path(
        "auth/password/reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="auth_password_reset_confirm",
    ),
    path(
        "auth/password/change/",
        PasswordChangeView.as_view(),
        name="auth_password_change",
    ),
    # Email verification
    path(
        "auth/email/verify/",
        EmailVerificationView.as_view(),
        name="auth_email_verify",
    ),
    # CSRF token
    path("auth/csrf/", CSRFTokenView.as_view(), name="csrf_token"),
    # Profile
    path("profile/avatar/", ProfileAvatarView.as_view(), name="profile_avatar"),
]
