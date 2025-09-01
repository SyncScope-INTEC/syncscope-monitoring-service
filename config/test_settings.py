"""
Test settings for syncscope-monitoring-service.
"""

from .settings import *
import os

# Override settings for testing
DEBUG = True
SECRET_KEY = "test-secret-key-for-testing-only"
USE_SQLITE = True

# Use SQLite for testing
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Disable Redis caching for tests
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

# Disable Celery for tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Disable rate limiting for tests
RATELIMIT_ENABLE = False

# Simple logging for tests
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "apps.monitoring": {
            "handlers": ["console"],
            "level": "INFO",
        },
    },
}

# Disable CORS checks for tests
CORS_ALLOW_ALL_ORIGINS = True

# Fast password hashing for tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Disable migrations for faster tests
class DisableMigrations:
    def __contains__(self, item):
        return True
    def __getitem__(self, item):
        return None

MIGRATION_MODULES = DisableMigrations()

# Test-specific environment
ENVIRONMENT = "testing"