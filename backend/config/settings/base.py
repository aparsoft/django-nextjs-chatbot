# /home/ram/aparsoft/backend/config/settings/base.py

from pathlib import Path
import sys
import os
from decouple import config

# Set USER_AGENT for PRAW (Reddit API)
os.environ.setdefault(
    "USER_AGENT", config("USER_AGENT", default="APARSOFT_Content_Generator_1.0")
)

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Add the 'apps' directory to the Python path
sys.path.insert(0, str(BASE_DIR / "apps"))

DJANGO_APPS = [
    "jazzmin",
    "daphne",
    "channels",
    "django.contrib.admin",
    "django.contrib.sites",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    #### Third Party Apps #####
    "django_filters",
    "rest_framework",
    "rest_framework.authtoken",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",  # for API documentation
    "drf_spectacular_sidecar",  # required for Django collectstatic discovery
    "django_celery_results",
    "django_celery_beat",
    "corsheaders",  # Cross Origin
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
]

LOCAL_APPS = [
    "accounts",
    "chatbot",
    "core",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

DJANGO_ALLOW_ASYNC_UNSAFE = False  # Enforce async safety

# Async view configurations
REST_FRAMEWORK_ASYNC_VIEWS = True  # Enable support for async views in DRF

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

AUTH_USER_MODEL = "accounts.CustomUser"

MASTER_ENCRYPTION_KEY = config("MASTER_ENCRYPTION_KEY", default="")
# Current version of the encryption key
ENCRYPTION_KEY_VERSION = 1

# Minimum version that is still considered valid
ENCRYPTION_MIN_VERSION = 1

# Maximum version (usually same as current)
ENCRYPTION_MAX_VERSION = 1

X_FRAME_OPTIONS = "SAMEORIGIN"

CONTENT_PERM_CACHE_TIMEOUT = 3600

# LLM and Embedding configurations
GPT_MINI = "gpt-4o-mini"
GPT_MINI_STRING = "openai/gpt-4o-mini"
REQUEST_GPT_TIMEOUT = 30
GRAPH_CONFIG = {
    "recursion_limit": 100,
    "max_retries": 5,
    "error_policy": "stop",  # or "continue" based on requirements
}


CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100
SPLITTER_TYPE = "recursive"  # "token", "recursive"
MAX_RETRIES = 3
DEFAULT_LLM_MODEL = "gpt-4o-mini"
EMBEDDING_MODEL = "text-embedding-3-small"
MAX_CONCURRENT = 3
BATCH_TIMEOUT_MINUTES = 60

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_L10N = True
USE_TZ = True
SITE_ID = 1

ROOT_URLCONF = "config.urls"

accept_content = ["application/json"]
task_serializer = "json"
result_serializer = "json"

# Celery Configuration Options
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60

# For session cache
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
SESSION_CACHE_ALIAS = "default"

SPECTACULAR_SETTINGS = {
    # Basic API info
    "TITLE": "Aparsoft Chatbot API",
    "DESCRIPTION": "AI-Powered Technology Solutions and Digital Transformation Provider API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # UI settings
    "SWAGGER_UI_DIST": "SIDECAR",  # shorthand to use the sidecar instead
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
    # Schema configuration
    "SCHEMA_PATH_PREFIX": "/api/v[0-9]",  # Include only API paths
    "COMPONENT_SPLIT_REQUEST": True,
    "COMPONENT_NO_READ_ONLY_REQUIRED": False,
    "SERVERS": [{"url": "/api/v1"}],  # This specifies the base URL for the API
    # Authentication settings
    "SECURITY": [{"Bearer": []}],
    # Tag configuration
    # "TAGS": [
    #     {"name": "Accounts", "description": "Authentication and user management"},
    #     {"name": "Core", "description": "Core functionality"},
    #     {"name": "Customers", "description": "Customer management"},
    #     {"name": "WorkItems", "description": "Work items and tasks"},
    # ],
    # Additional customization
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "persistAuthorization": True,
        "displayOperationId": False,
        "defaultModelsExpandDepth": 3,
        "defaultModelExpandDepth": 3,
        "defaultModelRendering": "model",
        "displayRequestDuration": True,
        "docExpansion": "none",
        "filter": True,
        "showExtensions": True,
        "showCommonExtensions": True,
        "tryItOutEnabled": True,
    },
    # Preprocessing and extensions
    "ENUM_NAME_OVERRIDES": {},
    "PREPROCESSING_HOOKS": [],
    "POSTPROCESSING_HOOKS": [],
    "APPEND_COMPONENTS": {},
    "EXTENSIONS_HOOK": None,
}


# Jazzmin Settings
JAZZMIN_SETTINGS = {
    "site_title": "Admin Portal",
    "site_header": "Aparsoft Admin",
    "site_brand": "Admin",
    "welcome_sign": "Welcome to the Admin Portal",
    "copyright": "aparsoft",
    "search_model": ["accounts.CustomUser", "auth.Group"],
    "user_model": "accounts.CustomUser",
    "user_avatar": None,
    "usermenu_links": [],
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    # List of apps and models to exclude from the admin
    "hide_models": ["auth.User"],
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "accounts": "fas fa-user-circle",
        "core": "fas fa-cog",
        "socialaccount.socialapp": "fas fa-share-alt",
        "socialaccount.socialtoken": "fas fa-key",
        "socialaccount.socialaccount": "fas fa-user-circle",
    },
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
    "related_modal_active": True,
    "custom_css": None,
    "custom_js": None,
    "show_ui_builder": True,
    "changeform_format": "horizontal_tabs",
    "changeform_format_overrides": {
        "auth.user": "collapsible",
        "auth.group": "vertical_tabs",
    },
    "custom_links": {},
    "order_with_respect_to": ["auth", "accounts", "core", "socialaccount"],
    "icons_per_app": {
        "socialaccount": {
            "models": {
                "socialapp": "fas fa-share-alt",
                "socialtoken": "fas fa-key",
                "socialaccount": "fas fa-user-circle",
            },
        },
    },
}

__version__ = "0.1.0"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
