"""
User Tool Model - Custom tools/functions users can enable.

Tools are defined in code (see TOOL_REGISTRY below) and users can
enable/disable them with per-user configuration.

AvailableTool was intentionally removed — for an intern onboarding project,
tool definitions belong in code (management commands / constants), not a
separate DB table.  This keeps the model count down and teaches the
"code-first configuration" pattern.
"""

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from core.models import TimestampedModel


# ---------------------------------------------------------------------------
# Tool Registry — single source of truth for available tools
# ---------------------------------------------------------------------------
# Add new tools here; a management command can seed UserTool rows from this.

TOOL_REGISTRY = {
    "web_search": {
        "display_name": "Web Search",
        "description": "Search the web for up-to-date information using Tavily.",
        "category": "search",
        "icon": "🔍",
        "default_config": {"max_results": 5},
    },
    "code_executor": {
        "display_name": "Code Executor",
        "description": "Execute Python code snippets in a sandboxed environment.",
        "category": "code",
        "icon": "💻",
        "default_config": {"timeout_seconds": 30},
    },
    "calculator": {
        "display_name": "Calculator",
        "description": "Perform mathematical calculations and conversions.",
        "category": "utility",
        "icon": "🧮",
        "default_config": {},
    },
    "document_retriever": {
        "display_name": "Document Retriever",
        "description": "Search through your uploaded documents using semantic search.",
        "category": "search",
        "icon": "📄",
        "default_config": {"top_k": 5},
    },
}

TOOL_CATEGORY_CHOICES = [
    ("search", "Search & Retrieval"),
    ("code", "Code Execution"),
    ("data", "Data Processing"),
    ("integration", "External Integration"),
    ("utility", "Utility"),
    ("custom", "Custom"),
]


class UserTool(TimestampedModel):
    """
    Track which tools/functions users have enabled.

    Tools are defined in TOOL_REGISTRY but users can enable/disable them
    and configure their settings independently.
    """

    # User association
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="enabled_tools",
        help_text=_("User who configured this tool"),
    )

    # Tool identification
    tool_name = models.CharField(
        max_length=100,
        help_text=_('Internal name of the tool (e.g., "web_search", "code_executor")'),
    )

    tool_display_name = models.CharField(
        max_length=255, help_text=_("Human-readable tool name")
    )

    # Enable/disable
    is_enabled = models.BooleanField(
        default=True, help_text=_("Whether this tool is enabled for the user")
    )

    # Tool configuration
    configuration = models.JSONField(
        default=dict, blank=True, help_text=_("Tool-specific configuration settings")
    )

    # Tool metadata
    description = models.TextField(
        blank=True, null=True, help_text=_("Description of what this tool does")
    )

    category = models.CharField(
        max_length=50,
        default="general",
        choices=TOOL_CATEGORY_CHOICES,
        help_text=_("Tool category"),
    )

    icon = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        help_text=_("Emoji or icon for UI display"),
    )

    # Usage tracking
    usage_count = models.IntegerField(
        default=0, help_text=_("Number of times this tool has been used")
    )

    last_used_at = models.DateTimeField(
        null=True, blank=True, help_text=_("When this tool was last used")
    )

    # Rate limiting
    rate_limit = models.IntegerField(
        null=True, blank=True, help_text=_("Maximum uses per hour (null = unlimited)")
    )

    rate_limit_period = models.CharField(
        max_length=20,
        default="hour",
        choices=[
            ("minute", "Per Minute"),
            ("hour", "Per Hour"),
            ("day", "Per Day"),
        ],
        help_text=_("Rate limit period"),
    )

    # Permissions
    requires_approval = models.BooleanField(
        default=False, help_text=_("Whether tool usage requires admin approval")
    )

    is_approved = models.BooleanField(
        default=True, help_text=_("Whether usage is approved by admin")
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_tools",
        help_text=_("Admin who approved this tool"),
    )

    approved_at = models.DateTimeField(
        null=True, blank=True, help_text=_("When this tool was approved")
    )

    class Meta:
        verbose_name = _("User Tool")
        verbose_name_plural = _("User Tools")
        ordering = ["tool_display_name"]
        unique_together = ["user", "tool_name"]
        indexes = [
            models.Index(
                fields=["user", "is_enabled"], name="usertool_user_enabled_idx"
            ),
            models.Index(fields=["tool_name"], name="usertool_name_idx"),
            models.Index(fields=["category"], name="usertool_category_idx"),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.tool_display_name}"

    # ------------------------------------------------------------------
    # Instance methods — fatty model, thin viewset
    # ------------------------------------------------------------------

    def activate(self):
        """Enable this tool for the user."""
        self.is_enabled = True
        self.save(update_fields=["is_enabled"])

    def deactivate(self):
        """Disable this tool for the user."""
        self.is_enabled = False
        self.save(update_fields=["is_enabled"])

    def increment_usage(self):
        """Increment usage count and update last used timestamp."""
        from django.utils import timezone

        self.usage_count += 1
        self.last_used_at = timezone.now()
        self.save(update_fields=["usage_count", "last_used_at"])

    def reset_usage(self):
        """Reset usage counter (e.g., after rate-limit window resets)."""
        self.usage_count = 0
        self.save(update_fields=["usage_count"])

    def approve(self, approved_by_user):
        """Approve this tool for use by an admin."""
        from django.utils import timezone

        self.is_approved = True
        self.approved_by = approved_by_user
        self.approved_at = timezone.now()
        self.save(update_fields=["is_approved", "approved_by", "approved_at"])

    def get_effective_config(self):
        """
        Return merged configuration: TOOL_REGISTRY defaults + user overrides.

        User overrides take precedence so interns can see how JSON config
        merging works in practice.
        """
        registry_entry = TOOL_REGISTRY.get(self.tool_name, {})
        defaults = registry_entry.get("default_config", {})
        merged = {**defaults, **self.configuration}
        return merged

    def get_display_info(self):
        """
        Return a dict of display-friendly information for the frontend.

        Useful in serializers — just call `tool.get_display_info()` instead
        of building the dict in the viewset.
        """
        return {
            "tool_name": self.tool_name,
            "display_name": self.tool_display_name,
            "description": self.description,
            "category": self.get_category_display(),
            "icon": self.icon,
            "is_enabled": self.is_enabled,
            "usage_count": self.usage_count,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
        }

    def check_rate_limit(self):
        """
        Check if user has exceeded rate limit.

        Returns:
            dict: {'allowed': bool, 'remaining': int, 'reset_at': datetime}
        """
        from django.utils import timezone
        from datetime import timedelta

        if not self.rate_limit:
            return {"allowed": True, "remaining": None, "reset_at": None}

        # Calculate time window
        now = timezone.now()
        if self.rate_limit_period == "minute":
            window_start = now - timedelta(minutes=1)
        elif self.rate_limit_period == "hour":
            window_start = now - timedelta(hours=1)
        else:  # day
            window_start = now - timedelta(days=1)

        # Count recent usage
        from .token_usage import TokenUsage

        recent_usage = TokenUsage.objects.filter(
            user=self.user,
            created_at__gte=window_start,
            metadata__tool_name=self.tool_name,
        ).count()

        remaining = max(0, self.rate_limit - recent_usage)
        allowed = recent_usage < self.rate_limit

        # Calculate reset time
        if self.rate_limit_period == "minute":
            reset_at = now + timedelta(minutes=1)
        elif self.rate_limit_period == "hour":
            reset_at = now + timedelta(hours=1)
        else:
            reset_at = now + timedelta(days=1)

        return {
            "allowed": allowed,
            "remaining": remaining,
            "reset_at": reset_at,
            "current_usage": recent_usage,
            "limit": self.rate_limit,
        }

    # ------------------------------------------------------------------
    # Class methods / queryset helpers
    # ------------------------------------------------------------------

    @classmethod
    def get_user_tools(cls, user, enabled_only=True):
        """Get all tools for a user."""
        queryset = cls.objects.filter(user=user)

        if enabled_only:
            queryset = queryset.filter(is_enabled=True, is_approved=True)

        return queryset

    @classmethod
    def get_enabled_for_user(cls, user):
        """Get enabled + approved tools for a user (ready to use with LangGraph)."""
        return list(
            cls.objects.filter(user=user, is_enabled=True, is_approved=True)
        )

    @classmethod
    def get_tool_config(cls, user, tool_name):
        """Get merged configuration for a specific tool."""
        try:
            tool = cls.objects.get(user=user, tool_name=tool_name)
            return tool.get_effective_config()
        except cls.DoesNotExist:
            # Fall back to registry defaults
            return TOOL_REGISTRY.get(tool_name, {}).get("default_config", {})

    @classmethod
    def enable_tool(cls, user, tool_name, configuration=None):
        """
        Enable a tool from the registry for a user.

        Args:
            user: The user
            tool_name: Must exist in TOOL_REGISTRY
            configuration: Optional user overrides

        Returns:
            UserTool instance

        Raises:
            ValueError: If tool_name not in TOOL_REGISTRY
        """
        if tool_name not in TOOL_REGISTRY:
            raise ValueError(
                f"Unknown tool '{tool_name}'. "
                f"Available: {', '.join(TOOL_REGISTRY.keys())}"
            )

        registry_entry = TOOL_REGISTRY[tool_name]

        user_tool, created = cls.objects.get_or_create(
            user=user,
            tool_name=tool_name,
            defaults={
                "tool_display_name": registry_entry["display_name"],
                "description": registry_entry["description"],
                "category": registry_entry["category"],
                "icon": registry_entry.get("icon", ""),
                "is_enabled": True,
                "configuration": configuration or registry_entry.get("default_config", {}),
            },
        )

        if not created:
            user_tool.is_enabled = True
            if configuration:
                user_tool.configuration = configuration
            user_tool.save()

        return user_tool

    @classmethod
    def disable_tool(cls, user, tool_name):
        """Disable a tool for a user."""
        cls.objects.filter(user=user, tool_name=tool_name).update(is_enabled=False)

    @classmethod
    def bulk_enable(cls, user, tool_names):
        """
        Enable multiple tools at once.

        Args:
            user: The user
            tool_names: List of tool names from TOOL_REGISTRY

        Returns:
            List of UserTool instances
        """
        enabled = []
        for tool_name in tool_names:
            tool = cls.enable_tool(user, tool_name)
            enabled.append(tool)
        return enabled

    @classmethod
    def seed_all_tools(cls, user):
        """
        Create UserTool entries for every tool in TOOL_REGISTRY.

        Useful in a management command or post-registration signal.
        """
        seeded = []
        for tool_name in TOOL_REGISTRY:
            tool, created = cls.objects.get_or_create(
                user=user,
                tool_name=tool_name,
                defaults={
                    "tool_display_name": TOOL_REGISTRY[tool_name]["display_name"],
                    "description": TOOL_REGISTRY[tool_name]["description"],
                    "category": TOOL_REGISTRY[tool_name]["category"],
                    "icon": TOOL_REGISTRY[tool_name].get("icon", ""),
                    "is_enabled": False,  # Disabled by default — user opts in
                },
            )
            seeded.append((tool, created))
        return seeded
