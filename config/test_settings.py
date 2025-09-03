"""
Test settings for syncscope-monitoring-service.
"""

import os

from .settings import *

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

# Use memory cache for tests (real cache backend)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",
    }
}

# Disable Celery for tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Disable rate limiting for tests
RATELIMIT_ENABLE = False

# Remove ratelimit from installed apps to avoid cache errors
THIRD_PARTY_APPS = [app for app in THIRD_PARTY_APPS if app != "django_ratelimit"]
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# Override Redis settings to avoid connection errors in tests
REDIS_URL = "redis://localhost:6379/0"
REDIS_CACHE_URL = "redis://localhost:6379/1"

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
    "django.contrib.auth.hashers.MD5PasswordHasher",
]


# Enable migrations for tests so tables are created
# MIGRATION_MODULES = DisableMigrations()  # Disabled for proper test setup

# Test-specific environment
ENVIRONMENT = "testing"
