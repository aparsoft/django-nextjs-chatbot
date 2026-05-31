# config/urls.py
import logging
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from typing import List, Union, Tuple, TypeAlias
from django.urls.resolvers import URLPattern, URLResolver
from rest_framework import permissions
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

# Configure logging with proper formatting
logger = logging.getLogger(__name__)


# Type aliases for better code readability and maintainability
URLPatternsList: TypeAlias = List[Union[URLPattern, URLResolver]]
URLPatternsNamespace: TypeAlias = Tuple[List[Union[URLPattern, URLResolver]], str]

# API v1 URL patterns - Core API endpoints
api_v1_patterns: URLPatternsList = [
    # Django Spectacular API documentation
    path("schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path(
        "docs/",
        SpectacularSwaggerView.as_view(url_name="api_v1:api-schema"),
        name="swagger-ui",
    ),
    path(
        "redoc/",
        SpectacularRedocView.as_view(url_name="api_v1:api-schema"),
        name="redoc",
    ),
    # Accounts/Authentication endpoints
    path("accounts/", include(("accounts.api.urls", "accounts"), namespace="accounts")),
    # Chatbot endpoints
    path("chatbot/", include(("chatbot.api.urls", "chatbot"), namespace="chatbot")),
]

# Main URL patterns with versioning support
urlpatterns: URLPatternsList = [
    # Admin interface
    path(f"{settings.ADMIN_URL}", admin.site.urls),
    # API v1 endpoints
    path("api/v1/", include((api_v1_patterns, "v1"), namespace="api_v1")),
    # Future API versions can be added here
    # path('api/v2/',
    #      include((api_v2_patterns, 'v2'),
    #             namespace='api_v2')
    # ),
    # Authentication URLs (allauth)
    # path('accounts/',
    #      include('allauth.urls')
    #      ),
]

# Serve static and media files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Type checking and validation
assert all(
    isinstance(pattern, (URLPattern, URLResolver)) for pattern in urlpatterns
), "All URL patterns must be either URLPattern or URLResolver instances"
