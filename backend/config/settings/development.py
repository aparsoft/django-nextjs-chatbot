# /home/ram/aparsoft/backend/config/settings/development.py

# config/settings/development.py

from .base import *
import os
from decouple import config
from datetime import timedelta

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# Create logs directory if it doesn't exist
LOGS_DIR = BASE_DIR / "logs"
if not LOGS_DIR.exists():
    os.makedirs(LOGS_DIR, exist_ok=True)

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Add the account middleware:
    "allauth.account.middleware.AccountMiddleware",
]

AUTHENTICATION_BACKENDS = (
    # 'users.backends.EmailBackend',
    # 'social_core.backends.google.GoogleOAuth2',
    # Needed to login by username in Django admin, regardless of `allauth`
    "django.contrib.auth.backends.ModelBackend",
    # `allauth` specific authentication methods, such as login by email
    "allauth.account.auth_backends.AuthenticationBackend",
)

# Postgres
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME", default="chatbotdb"),
        "USER": config("DB_USER", default="chatbot_user"),
        "PASSWORD": config("DB_PASSWORD", default="chatbot_pass"),
        "HOST": config("DB_HOST", default="localhost"),
        "PORT": config("DB_PORT", default="5432"),
        "OPTIONS": {
            "sslmode": "disable",  # Disables SSL for local development
        },
    }
}

STATIC_URL = "/static/"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]
# Ensure static files directory exists
STATIC_ROOT = BASE_DIR / "staticfiles"
STATIC_ROOT.mkdir(exist_ok=True)
if STATIC_ROOT.exists():
    os.chmod(STATIC_ROOT, 0o755)

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_ROOT.mkdir(exist_ok=True)
if MEDIA_ROOT.exists():
    os.chmod(MEDIA_ROOT, 0o755)

# File upload configurations
FILE_UPLOAD_PERMISSIONS = 0o644
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755
FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5 MB

STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
]

# Custom admin URL
ADMIN_URL = config("DJANGO_ADMIN_URL", default="chatbot-admin/")

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config(
    "DJANGO_SECRET_KEY",
    "django-insecure-p!1w7j+^j5v8y-@$_9j*8mr-)l#$u=08=c)!=(b1dleci18$7+",
)

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {
            "min_length": 8,
        },
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

DJANGO_PUBLIC_BASE_URL = config(
    "DJANGO_PUBLIC_BASE_URL", default="http://localhost:8000"
)
DJANGO_PUBLIC_API_URL = config(
    "DJANGO_PUBLIC_API_URL", default="http://localhost:8000/api/v1"
)


# API Keys
# Export keys from .env into os.environ so that third-party libraries
# (langchain, langchain_tavily, etc.) that read os.environ directly
# can pick them up.  python-decouple reads .env but does NOT export.
for _key in (
    "OPENAI_API_KEY",
    "HUGGINGFACEHUB_API_TOKEN",
    "TAVILY_API_KEY",
    "DEEPGRAM_API_KEY",
):
    if _key not in os.environ:
        os.environ[_key] = config(_key, default="")


# If you need separate keys for dev and prod, you can set them here
DEFAULT_LLM_PROVIDER = "openai"
DEFAULT_LLM_MODEL = "gpt-4o-mini"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
REQUEST_GPT_TIMEOUT = 30

CORS_ALLOW_CREDENTIALS = True
# CORS settings
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",  # Next.js development server
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://docserve.localhost:8000",
]

# CSRF Trusted Origins
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://docserve.localhost:8000",
]

PGVECTOR_CONNECTION_STRING = config(
    "PGVECTOR_CONNECTION_STRING",
    default="postgresql+psycopg://user:password@localhost:5432/vector_db",
)
PG_CHECKPOINT_URI = config(
    "PG_CHECKPOINT_URI",
    default="postgresql://user:password@localhost:5432/checkpoint_db",
)

# Fix the encoding issue - add these lines
if "\\x3a" in PGVECTOR_CONNECTION_STRING:
    PGVECTOR_CONNECTION_STRING = PGVECTOR_CONNECTION_STRING.replace("\\x3a", ":")


if "\\x3a" in PG_CHECKPOINT_URI:
    PG_CHECKPOINT_URI = PG_CHECKPOINT_URI.replace("\\x3a", ":")

# Normalize PG_CHECKPOINT_URI for psycopg compatibility
# SQLAlchemy uses 'postgresql+psycopg://' but raw psycopg expects 'postgresql://'
# AsyncPostgresSaver.from_conn_string() from langgraph uses raw psycopg
# NOTE: PGVECTOR_CONNECTION_STRING must KEEP 'postgresql+psycopg://' for SQLAlchemy/langchain-postgres
if PG_CHECKPOINT_URI.startswith("postgresql+psycopg://"):
    PG_CHECKPOINT_URI = PG_CHECKPOINT_URI.replace(
        "postgresql+psycopg://", "postgresql://"
    )

# Repair degenerate query strings like '?sslmode' (key with no value) which psycopg
# rejects by treating the entire URL as a single connection option. Default to
# sslmode=require which is what managed Postgres (DigitalOcean) needs.
if PG_CHECKPOINT_URI.endswith("?sslmode") or "?sslmode&" in PG_CHECKPOINT_URI:
    PG_CHECKPOINT_URI = PG_CHECKPOINT_URI.replace("?sslmode", "?sslmode=require")
if PG_CHECKPOINT_URI.endswith("&sslmode"):
    PG_CHECKPOINT_URI = PG_CHECKPOINT_URI[: -len("&sslmode")] + "&sslmode=require"


CSRF_COOKIE_SECURE = False  # Set to True in production with HTTPS
CSRF_COOKIE_HTTPONLY = False  # Set to True in production
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_USE_SESSIONS = False
CSRF_COOKIE_NAME = "csrftoken"

SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-csrf-token",
    "csrf-token",
    "csrftoken",
    "x-requested-with",
    "cache-control",
    "pragma",
    "expires",
]

# Redis and Celery Configuration
REDIS_URL = config("REDIS_URL", default="redis://localhost:6379/0")

# Celery Settings
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://localhost:6379/1")
CELERY_RESULT_BACKEND = config(
    "CELERY_RESULT_BACKEND", default="redis://localhost:6379/2"
)

# Celery Configuration Options
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"

# Broker and Result Backend Transport Options
CELERY_BROKER_TRANSPORT_OPTIONS = {
    "visibility_timeout": 3600,  # 1 hour
    "max_retries": 3,
}

CELERY_RESULT_BACKEND_TRANSPORT_OPTIONS = {
    "retry_policy": {
        "timeout": 5.0,
        "max_retries": 3,
    }
}

# Channel Layers Configuration (for Django Channels)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
            "capacity": 1500,
            "expiry": 20,
        },
    },
}

# Cache Configuration
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "db": "1",
            "pool_class": "redis.connection.ConnectionPool",
            "socket_timeout": 5,
            "socket_connect_timeout": 5,
            "retry_on_timeout": True,
            "max_connections": 100,
        },
        "KEY_PREFIX": "nlp_playground",
    }
}

# Base REST_FRAMEWORK settings (can be extended in environment settings)
REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": int(config("DJANGO_PAGINATION_LIMIT", 18)),
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        # "accounts.services.CustomJWTCookieAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/minute",
        "user": "200/minute",
        "login": "30/minute",
    },
}

# Security headers
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

SIMPLE_JWT = {
    # Token lifetimes
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    # Token rotation settings
    # Disable token rotation to prevent blacklisting issues
    "ROTATE_REFRESH_TOKENS": True,  # Enable rotation
    "BLACKLIST_AFTER_ROTATION": True,  # Enable blacklisting
    "UPDATE_LAST_LOGIN": False,  # Reduce DB hits
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    # Signing settings
    # 'ALGORITHM': 'HS256',
    # 'SIGNING_KEY': SECRET_KEY,
    # 'VERIFYING_KEY': None,
    # Token validation settings
    # 'AUDIENCE': None,
    # 'ISSUER': None,
    # Header settings
    # 'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    # User settings
    # 'USER_ID_FIELD': 'id',
    # 'USER_ID_CLAIM': 'user_id',
    # Token classes and claims
    # 'TOKEN_TYPE_CLAIM': 'token_type',
    # 'JTI_CLAIM': 'jti',
    # Additional security settings
    # 'TOKEN_USER_CLASS': 'django.contrib.auth.models.User',
    # Use them if required: sliding token settings
    # 'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
    # 'SLIDING_TOKEN_LIFETIME': timedelta(minutes=30),
    # 'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=1),
}

# Frontend URL for email links
FRONTEND_URL = config("NEXTAUTH_URL", default="http://localhost:3000")

# Newsletter email settings for development
CONTACT_EMAIL = config("CONTACT_EMAIL", default="contact@aparsoft.com")
AI_TEAM_EMAIL = config("AI_TEAM_EMAIL", default="ai@aparsoft.com")
ENTERPRISE_TEAM_EMAIL = config(
    "ENTERPRISE_TEAM_EMAIL", default="enterprise@aparsoft.com"
)
CONSULTING_TEAM_EMAIL = config(
    "CONSULTING_TEAM_EMAIL", default="consulting@aparsoft.com"
)
PARTNERSHIPS_EMAIL = config("PARTNERSHIPS_EMAIL", default="partnerships@aparsoft.com")
HR_EMAIL = config("HR_EMAIL", default="hr@aparsoft.com")
SUPPORT_EMAIL = config("SUPPORT_EMAIL", default="support@aparsoft.com")

# Email configuration for development (optional)
# Print emails to console
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="noreply@aparsoft.com")

# OAuth settings
OAUTH = {
    "GOOGLE": {
        "CLIENT_ID": "your-google-client-id",
        "CLIENT_SECRET": "your-google-client-secret",
        "REDIRECT_URI": "https://aparsoft.com/auth/callback/google",
    },
    "GITHUB": {
        "CLIENT_ID": "your-github-client-id",
        "CLIENT_SECRET": "your-github-client-secret",
        "REDIRECT_URI": "https://aparsoft.com/auth/callback/github",
    },
    # Add other OAuth providers as needed
}


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            # Added {name}
            "format": "[{asctime}] {levelname} [{name}] {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "simple": {
            "format": "[{levelname}] {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "level": "INFO",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",  # Changed to RotatingFileHandler
            "filename": BASE_DIR / "logs" / "dev-debug.log",
            "formatter": "verbose",
            "level": "INFO",
            "maxBytes": 1024 * 1024 * 5,  # 5 MB
            "backupCount": 5,
            "delay": True,  # Delay creation until first log record is written
        },
    },
    "loggers": {
        "": {  # Root logger
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": True,
        },
        "django": {
            "handlers": ["console", "file"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.server": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "accounts": {  # Your app logger
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "jazzmin": {
            "handlers": ["console", "file"],
            "level": "ERROR",  # Change to ERROR to suppress warnings
            "propagate": False,
        },
    },
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": False,
    "accent": "accent-primary",
    "navbar": "navbar-white navbar-light",
    "no_navbar_border": False,
    "navbar_fixed": False,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": False,
    "sidebar": "sidebar-dark-primary",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": False,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "cerulean",
    "dark_mode_theme": None,
    "button_classes": {
        "primary": "btn-outline-primary",
        "secondary": "btn-outline-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
}
