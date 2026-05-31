# config/settings/test.py

"""
Test settings — extends development settings with test-specific overrides.

Usage:
    python manage.py test accounts --settings=config.settings.test -v 2
"""

from .development import *  # noqa: F401,F403

# ---- Test-specific overrides ----

# Faster password hasher for tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Dummy cache for tests
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

# Celery: run tasks synchronously in tests
CELERY_TASK_ALWAYS_EAGER = True
