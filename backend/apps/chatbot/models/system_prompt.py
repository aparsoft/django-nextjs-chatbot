"""
System Prompt Template model — reusable, parameterised system prompts for AI.

This module defines :class:`SystemPromptTemplate`, which stores named,
categorised system prompts with optional ``{variable}`` placeholders that
are rendered at runtime via :meth:`render`.  Templates can be public
(shared across all users) or private, and exactly one can be marked as
the platform default (``is_default``).

Key design decisions
--------------------
- **SlugField + unique name** — ``slug`` is auto-populated from ``name``
  in the admin (``prepopulated_fields``) and used as a stable lookup key.
- **Variable templating** — ``variables`` declares the placeholders;
  :meth:`render` does simple ``{key}`` substitution; :meth:`validate_variables`
  checks for missing or extra keys.
- **Single default invariant** — :meth:`set_as_default` atomically clears
  the previous default before setting the new one, so only one template
  is ever ``is_default=True``.
- **Analytics** — ``usage_count``, ``rating_sum``, ``rating_count`` are
  denormalised counters updated via :meth:`increment_usage` and
  :meth:`add_rating`.

Typical usage
-------------
::

    # Get the default template
    template = SystemPromptTemplate.get_default()

    # Render with variables
    prompt = template.render({"user_name": "Alice", "topic": "Python"})

    # Validate before rendering
    result = template.validate_variables({"user_name": "Alice"})
    # → {"valid": False, "missing": ["topic"], "extra": []}

    # Search
    templates = SystemPromptTemplate.search_templates("coding")

Models defined
--------------
- :class:`SystemPromptTemplate` — named, categorised prompt with variable support.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import TimestampedModel


class SystemPromptTemplate(TimestampedModel):
    """
    Reusable system prompt templates.

    Allows admins and users to create and share system prompts
    for different use cases (coding assistant, writing helper, etc.)
    """

    # Identification
    name = models.CharField(
        max_length=255, unique=True, help_text=_("Unique name for this prompt template")
    )

    slug = models.SlugField(
        max_length=255, unique=True, help_text=_("URL-friendly slug")
    )

    # Content
    content = models.TextField(help_text=_("The system prompt content"))

    description = models.TextField(
        blank=True, null=True, help_text=_("Description of what this prompt does")
    )

    # Categorization
    category = models.CharField(
        max_length=50,
        default="general",
        choices=[
            ("general", "General Purpose"),
            ("coding", "Coding Assistant"),
            ("writing", "Writing Helper"),
            ("research", "Research Assistant"),
            ("education", "Educational"),
            ("business", "Business/Professional"),
            ("creative", "Creative Writing"),
            ("analysis", "Data Analysis"),
            ("custom", "Custom"),
        ],
        help_text=_("Category of this prompt template"),
    )

    tags = models.JSONField(
        default=list, blank=True, help_text=_("Tags for organization and search")
    )

    # Usage settings
    is_default = models.BooleanField(
        default=False, help_text=_("Whether this is the default system prompt")
    )

    is_active = models.BooleanField(
        default=True, help_text=_("Whether this template is active and available")
    )

    is_public = models.BooleanField(
        default=False,
        help_text=_("Whether this template is publicly available to all users"),
    )

    # Variables and customization
    variables = models.JSONField(
        default=list,
        blank=True,
        help_text=_(
            "List of variables that can be replaced in the prompt (e.g., {user_name}, {topic})"
        ),
    )

    example_variables = models.JSONField(
        default=dict, blank=True, help_text=_("Example values for variables")
    )

    # Recommended settings
    recommended_model = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text=_("Recommended AI model for this prompt"),
    )

    recommended_temperature = models.FloatField(
        null=True, blank=True, help_text=_("Recommended temperature setting")
    )

    # Analytics
    usage_count = models.IntegerField(
        default=0, help_text=_("Number of times this template has been used")
    )

    rating_sum = models.IntegerField(default=0, help_text=_("Sum of all ratings"))

    rating_count = models.IntegerField(default=0, help_text=_("Number of ratings"))

    class Meta:
        verbose_name = _("System Prompt Template")
        verbose_name_plural = _("System Prompt Templates")
        ordering = ["-is_default", "-usage_count", "name"]
        indexes = [
            models.Index(
                fields=["category", "is_active"], name="sysprompt_cat_active_idx"
            ),
            models.Index(fields=["is_default"], name="sysprompt_default_idx"),
            models.Index(fields=["-usage_count"], name="sysprompt_usage_idx"),
        ]

    def __str__(self):
        return self.name

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def average_rating(self):
        """Calculate average rating."""
        if self.rating_count > 0:
            return round(self.rating_sum / self.rating_count, 2)
        return 0.0

    @property
    def has_variables(self):
        """Check if this template uses any variables."""
        return bool(self.variables)

    # ------------------------------------------------------------------
    # Instance methods
    # ------------------------------------------------------------------

    def increment_usage(self):
        """Increment usage count."""
        self.usage_count += 1
        self.save(update_fields=["usage_count"])

    def add_rating(self, rating_value):
        """
        Add a rating (1-5 stars).

        Args:
            rating_value: Integer from 1 to 5

        Returns:
            float: New average rating

        Raises:
            ValueError: If rating_value not in 1-5 range
        """
        if not 1 <= rating_value <= 5:
            raise ValueError(f"Rating must be 1-5, got {rating_value}")

        self.rating_sum += rating_value
        self.rating_count += 1
        self.save(update_fields=["rating_sum", "rating_count"])
        return self.average_rating

    def render(self, variables=None):
        """
        Render the prompt with variables.

        Args:
            variables: dict of variable values

        Returns:
            str: Rendered prompt with variables replaced
        """
        prompt = self.content

        if variables:
            for key, value in variables.items():
                placeholder = "{" + key + "}"
                prompt = prompt.replace(placeholder, str(value))

        return prompt

    def get_unfilled_variables(self):
        """
        Return list of variable placeholders still in the template content.

        Parses {variable_name} patterns from the content string.
        Useful for showing users which variables they need to fill.

        Returns:
            list of str: Variable names found in content
        """
        import re

        placeholders = re.findall(r"\{(\w+)\}", self.content)
        return list(set(placeholders))

    def validate_variables(self, provided_variables):
        """
        Check if all required variables are provided.

        Args:
            provided_variables: dict of variable_name -> value

        Returns:
            dict: {'valid': bool, 'missing': list, 'extra': list}
        """
        required = set(self.get_unfilled_variables())
        provided = set(provided_variables.keys())

        return {
            "valid": required.issubset(provided),
            "missing": list(required - provided),
            "extra": list(provided - required),
        }

    def duplicate(self, new_name=None, user=None):
        """
        Create a copy of this template.

        Args:
            new_name: Name for the duplicate (defaults to "{original} (Copy)")
            user: Optional user who is duplicating (for audit)

        Returns:
            SystemPromptTemplate: The new template instance
        """
        from django.utils.text import slugify

        name = new_name or f"{self.name} (Copy)"

        return SystemPromptTemplate.objects.create(
            name=name,
            slug=slugify(name),
            content=self.content,
            description=self.description,
            category=self.category,
            tags=list(self.tags),
            variables=list(self.variables),
            example_variables=dict(self.example_variables),
            recommended_model=self.recommended_model,
            recommended_temperature=self.recommended_temperature,
            is_default=False,  # Never duplicate default flag
            is_public=False,
        )

    def to_display_dict(self):
        """
        Return a serializable dict for API responses.
        """
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "category": self.category,
            "category_display": self.get_category_display(),
            "tags": self.tags,
            "has_variables": self.has_variables,
            "variables": self.variables,
            "example_variables": self.example_variables,
            "recommended_model": self.recommended_model,
            "recommended_temperature": self.recommended_temperature,
            "usage_count": self.usage_count,
            "average_rating": self.average_rating,
            "is_default": self.is_default,
            "is_public": self.is_public,
        }

    # ------------------------------------------------------------------
    # Class methods
    # ------------------------------------------------------------------

    @classmethod
    def get_default(cls):
        """Get the default system prompt template."""
        return cls.objects.filter(is_default=True, is_active=True).first()

    @classmethod
    def get_public_templates(cls):
        """Get all public templates."""
        return cls.objects.filter(is_public=True, is_active=True)

    @classmethod
    def get_by_category(cls, category):
        """Get templates by category."""
        return cls.objects.filter(category=category, is_active=True)

    @classmethod
    def get_for_session(cls, category=None):
        """
        Get templates suitable for creating a new session.

        Returns public + default templates, optionally filtered by category.

        Args:
            category: Optional category filter

        Returns:
            QuerySet
        """
        qs = cls.objects.filter(is_active=True).filter(
            models.Q(is_public=True) | models.Q(is_default=True)
        )

        if category:
            qs = qs.filter(category=category)

        return qs.order_by("-is_default", "-usage_count")

    @classmethod
    def search_templates(cls, query):
        """
        Search templates by name, description, or content.

        Args:
            query: Search string

        Returns:
            QuerySet matching templates
        """
        return cls.objects.filter(
            models.Q(name__icontains=query)
            | models.Q(description__icontains=query)
            | models.Q(content__icontains=query),
            is_active=True,
        ).order_by("-usage_count")
