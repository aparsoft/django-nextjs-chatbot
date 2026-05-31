"""
Custom Django user model for chatbot application.
Supports basic user management with email authentication, roles, and profile features.
"""

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
import logging
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.contrib.postgres.indexes import GinIndex

from core.models import TimestampedModel, Country

from ..utils import helper

logger = logging.getLogger(__name__)


class CustomUser(AbstractUser):
    """Custom user model for chatbot application with email-based authentication."""

    ROLE_CHOICES = [
        ("user", "User"),
        ("admin", "Administrator"),
    ]

    # Core fields
    email = models.EmailField(
        _("email address"),
        unique=True,
        help_text=_("Primary email address used for account identification"),
    )

    # Role field
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="user",
        help_text=_("User role determines access level"),
    )

    # Profile management
    profile_picture = models.ImageField(
        upload_to="avatars/",
        blank=True,
        null=True,
        help_text=_("User profile picture/avatar"),
    )

    # Verification and security
    email_verified = models.BooleanField(
        default=False, help_text=_("Indicates if the email address has been verified")
    )
    phone_verified = models.BooleanField(
        default=False, help_text=_("Indicates if the phone number has been verified")
    )
    two_factor_enabled = models.BooleanField(
        default=False, help_text=_("Indicates if two-factor authentication is enabled")
    )
    last_password_change = models.DateTimeField(
        auto_now_add=True, help_text=_("Timestamp of the last password change")
    )

    # Social auth
    social_auth_providers = models.JSONField(
        default=helper.get_default_social_auth_providers,
        help_text=_("Connected social authentication providers"),
    )

    # Activity tracking
    last_active = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Timestamp of the user's last platform activity"),
    )
    login_count = models.PositiveIntegerField(
        default=0, help_text=_("Number of times the user has logged in")
    )

    # Override groups and user_permissions to avoid clashes
    groups = models.ManyToManyField(
        "auth.Group",
        verbose_name=_("groups"),
        blank=True,
        help_text=_("The groups this user belongs to."),
        related_name="customuser_set",
        related_query_name="customuser",
    )
    user_permissions = models.ManyToManyField(
        "auth.Permission",
        verbose_name=_("user permissions"),
        blank=True,
        help_text=_("Specific permissions for this user."),
        related_name="customuser_set",
        related_query_name="customuser",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        ordering = ["-date_joined"]
        app_label = "accounts"
        indexes = [
            models.Index(fields=["email"], name="user_email_idx"),
            models.Index(fields=["username"], name="user_username_idx"),
            models.Index(fields=["role"], name="user_role_idx"),
            models.Index(fields=["last_active"], name="user_last_active_idx"),
            models.Index(fields=["date_joined"], name="user_date_joined_idx"),
            models.Index(fields=["email_verified"], name="user_email_verified_idx"),
            models.Index(
                fields=["email_verified", "last_active"],
                name="user_verified_active_idx",
            ),
            GinIndex(fields=["social_auth_providers"], name="user_social_auth_gin_idx"),
        ]

    def __str__(self) -> str:
        return self.email

    @property
    def full_name(self) -> str:
        """Return user's full name or username."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username

    @property
    def account_age_days(self) -> int:
        """Get account age in days."""
        return (timezone.now() - self.date_joined).days

    @property
    def is_admin_user(self) -> bool:
        """Check if user is an admin."""
        return self.role == "admin"

    def update_last_active(self, save: bool = True) -> None:
        """Update user's last active timestamp."""
        self.last_active = timezone.now()
        if save:
            self.save(update_fields=["last_active"])

    def verify_email(self) -> bool:
        """Verify user's email address."""
        if not self.email_verified:
            self.email_verified = True
            self.save(update_fields=["email_verified"])
            return True
        return False


class UserContact(TimestampedModel):
    """User contact information."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="contact"
    )
    address_line1 = models.CharField(max_length=255, blank=True, null=True)
    address_line2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)
    country = models.ForeignKey(
        Country,
        on_delete=models.SET_DEFAULT,
        default=1,
        null=True,
        help_text=_("Country of residence"),
    )
    contact_info = models.JSONField(
        default=helper.get_default_user_contact_info,
        null=True,
        blank=True,
        help_text=_(
            "Structured contact information including phones and social profiles"
        ),
    )
    billing_details = models.JSONField(
        default=dict,
        null=True,
        blank=True,
        help_text=_("Billing information for invoicing"),
    )

    timezone = models.CharField(
        max_length=100, blank=True, null=True, help_text=_("User timezone")
    )

    availability = models.JSONField(
        default=dict, null=True, blank=True, help_text=_("User availability schedule")
    )

    class Meta:
        indexes = [
            models.Index(fields=["user"], name="user_contact_user_idx"),
            GinIndex(fields=["contact_info"], name="user_contact_info_gin_idx"),
            GinIndex(fields=["billing_details"], name="user_billing_gin_idx"),
            GinIndex(fields=["availability"], name="user_availability_gin_idx"),
        ]

    def __str__(self) -> str:
        return f"Contact for {self.user.email}"
