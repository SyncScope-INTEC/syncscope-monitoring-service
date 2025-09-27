"""
Django settings for syncscope-monitoring-service project.
"""

import os
import sys
from datetime import timedelta
from pathlib import Path

import dj_database_url
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("SECRET_KEY")

DEBUG = config("DEBUG", default=True, cast=bool)

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1").split(",")

# Add Railway health check domain
if "RAILWAY_ENVIRONMENT" in os.environ:
    ALLOWED_HOSTS.extend(["healthcheck.railway.app", "*.railway.app", "*.up.railway.app"])

    # Add the specific Railway service domain if provided
    railway_public_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN")
    if railway_public_domain:
        ALLOWED_HOSTS.append(railway_public_domain)

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "corsheaders",
    "django_extensions",
    "drf_spectacular",
    "django_ratelimit",
]

LOCAL_APPS = [
    "apps.monitoring",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "apps.monitoring.middleware.SecurityHeadersMiddleware",
    "apps.monitoring.middleware.CORSPreflightMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "apps.monitoring.middleware.RequestLoggingMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.monitoring.middleware.RateLimitHeadersMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

# Database
DATABASE_URL = config("DATABASE_URL", default=None)
USE_SQLITE = config("USE_SQLITE", default=False, cast=bool)

if USE_SQLITE:
    # Use SQLite for local development
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
elif DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("DB_NAME", default="syncscope"),
            "USER": config("DB_USER", default="postgres"),
            "PASSWORD": config("DB_PASSWORD", default=""),
            "HOST": config("DB_HOST", default="localhost"),
            "PORT": config("DB_PORT", default="5432", cast=int),
        }
    }

# Database connection configuration for PostgreSQL only
if not USE_SQLITE:
    db_options = {
        "connect_timeout": 10,
        "application_name": "syncscope-monitoring-serverless",
    }

    # Schema configuration
    # This monitoring service works primarily with the monitoring schema
    use_monitoring_schema = (
        "test" not in config("DB_NAME", default="").lower() and "test" not in os.environ.get("DATABASE_URL", "").lower()
    )

    if use_monitoring_schema:
        # Set search path to include all schemas with monitoring as priority
        db_options["options"] = (
            "-c search_path=monitoring,auth,management,analytics,alerts,audit,public -c statement_timeout=30000"
        )
    else:
        db_options["options"] = "-c statement_timeout=30000"

    DATABASES["default"].update(
        {"CONN_MAX_AGE": 0, "CONN_HEALTH_CHECKS": True, "OPTIONS": db_options}  # Don't persist connections in serverless
    )

# Test database configuration
if "test" in sys.argv or "pytest" in sys.modules:
    # Force SQLite for tests to avoid connection issues and schema complexity
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",  # In-memory database for faster tests
        }
    }

# Password validation
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

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATICFILES_DIRS = [
    BASE_DIR / "apps" / "monitoring" / "static",
]

# WhiteNoise configuration for static files serving
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Custom User model for UUID compatibility
# Only use custom User model in production where it's safe
# In CI/test environments, we use the default auth.User
import sys

if "test" not in sys.argv and "pytest" not in sys.modules and not os.environ.get("GITHUB_ACTIONS"):
    AUTH_USER_MODEL = "monitoring.User"

# Authentication backends for admin integration with auth service API
# Only use custom auth backend in production where it's safe
if "test" not in sys.argv and "pytest" not in sys.modules and not os.environ.get("GITHUB_ACTIONS"):
    AUTHENTICATION_BACKENDS = [
        "apps.monitoring.database_auth_backend.CachedAuthServiceAPIBackend",
        # Removed ModelBackend to prevent auth_user table queries
    ]
else:
    # Use default auth backend for CI/test environments
    AUTHENTICATION_BACKENDS = [
        "django.contrib.auth.backends.ModelBackend",
    ]

# REST Framework configuration
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.monitoring.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "apps.monitoring.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.monitoring.exceptions.custom_exception_handler",
}

# CORS settings
CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS", default="http://localhost:3000,http://127.0.0.1:3000").split(",")
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = config("CORS_ALLOW_ALL_ORIGINS", default=True, cast=bool) and DEBUG
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://.*\.railway\.app$",  # Railway deployment domains
    r"^http://localhost:\d+$",  # Local development
    r"^http://127\.0\.0\.1:\d+$",  # Local development
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
    "x-requested-with",
    "x-service-token",  # For service-to-service communication
]
CORS_EXPOSE_HEADERS = [
    "content-length",
    "x-ratelimit-remaining",
    "x-ratelimit-limit",
    "x-ratelimit-reset",
]

# CSRF settings
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="http://localhost:3000,http://127.0.0.1:3000").split(",")

# Security settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG

# Proxy configuration for Railway
if "RAILWAY_ENVIRONMENT" in os.environ:
    USE_TZ = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = False  # Railway handles this

# Session security
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True

# Rate limiting
RATELIMIT_ENABLE = config("RATELIMIT_ENABLE", default=True, cast=bool)

# Environment for logging
ENVIRONMENT = config("ENVIRONMENT", default="development")

# Logging configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "structured": {
            "()": "apps.monitoring.logging_utils.StructuredFormatter",
        },
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "structured" if ENVIRONMENT == "production" else "simple",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": True,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "apps.monitoring": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": True,
        },
        "apps.monitoring.performance": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# Add file logging only in development or when writable directories exist
if DEBUG or os.access("/app", os.W_OK):
    LOGGING["handlers"]["structured_file"] = {
        "level": "INFO",
        "class": "logging.FileHandler",
        "filename": "/tmp/monitoring-structured.log" if not DEBUG else "monitoring-structured.log",
        "formatter": "structured",
    }
    LOGGING["handlers"]["file"] = {
        "level": "INFO",
        "class": "logging.FileHandler",
        "filename": "/tmp/django.log" if not DEBUG else "django.log",
        "formatter": "verbose",
    }

    # Update loggers to include file handlers
    for logger_name in ["django", "django.request", "apps.monitoring", "apps.monitoring.performance"]:
        if logger_name in LOGGING["loggers"]:
            LOGGING["loggers"][logger_name]["handlers"].extend(["structured_file", "file"])

# Cache configuration (Redis with fallback)
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": config("REDIS_URL", default="redis://127.0.0.1:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {
                "retry_on_timeout": True,
                "socket_connect_timeout": 5,
                "socket_timeout": 5,
                "health_check_interval": 30,
            },
            "IGNORE_EXCEPTIONS": True,  # Gracefully handle Redis failures
        },
        "KEY_PREFIX": "syncscope_monitoring",
        "TIMEOUT": 300,
    }
}

# API Documentation (Swagger/OpenAPI)
SPECTACULAR_SETTINGS = {
    "TITLE": "SyncScope Monitoring Service API",
    "DESCRIPTION": "SyncScope Monitoring Service API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SERVERS": [
        {"url": "http://localhost:8000", "description": "Local development server"},
        {"url": "http://127.0.0.1:8000", "description": "Local development server (127.0.0.1)"},
        {"url": "https://syncscope-monitoring-service-dev.up.railway.app", "description": "Development server"},
        {"url": "https://syncscope-monitoring-service-prod.up.railway.app", "description": "Production server"},
    ],
    "COMPONENT_SPLIT_PATCH": True,
    "COMPONENT_SPLIT_REQUEST": True,
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "persistAuthorization": True,
        "displayRequestDuration": True,
        "docExpansion": "tag",
        "filter": True,
        "showCommonExtensions": True,
    },
    "REDOC_UI_SETTINGS": {
        "hideDownloadButton": False,
        "hideHostname": False,
        "hideLoading": False,
        "lazyRendering": True,
        "menuToggle": True,
        "nativeScrollbars": False,
        "pathInMiddlePanel": True,
        "requiredPropsFirst": True,
        "scrollYOffset": 0,
        "theme": {
            "colors": {"primary": {"main": "#1976d2"}},
            "typography": {"fontSize": "14px"},
        },
    },
    "TAGS": [
        {
            "name": "Health",
            "description": "Service health check endpoints - no authentication required",
        },
        {
            "name": "Sessions",
            "description": "Developer monitoring session management - start, end, and retrieve sessions",
        },
        {
            "name": "Activities",
            "description": "Activity logging endpoints - individual activities and bulk uploads",
        },
        {
            "name": "Metrics",
            "description": "Code metrics and analysis data submission",
        },
        {
            "name": "Events",
            "description": "Git events and repository interaction tracking",
        },
    ],
    "EXTERNAL_DOCS": {
        "description": "SyncScope Platform Documentation",
        "url": "https://docs.syncscope.dev/monitoring-service/",
    },
    "CONTACT": {
        "name": "SyncScope API Support",
        "email": "api-support@syncscope.dev",
    },
    "LICENSE": {
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
}

# Service URLs for inter-service communication
AUTH_SERVICE_URL = config("AUTH_SERVICE_URL", default="https://syncscope-auth-service-dev.up.railway.app")
ANALYTICS_SERVICE_URL = config("ANALYTICS_SERVICE_URL", default="https://syncscope-analytics-service-dev.up.railway.app")
MANAGEMENT_SERVICE_URL = config("MANAGEMENT_SERVICE_URL", default="https://syncscope-management-service-dev.up.railway.app")
ALERTS_SERVICE_URL = config("ALERTS_SERVICE_URL", default="https://syncscope-alerts-service-dev.up.railway.app")

# JWT Configuration for service-to-service communication
JWT_SECRET_KEY = config("JWT_SECRET_KEY", default=SECRET_KEY)

# Celery Configuration
CELERY_BROKER_URL = config("REDIS_URL", default="redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = config("REDIS_URL", default="redis://127.0.0.1:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    "cleanup-expired-sessions": {
        "task": "apps.monitoring.tasks.cleanup_expired_sessions",
        "schedule": 3600.0,  # Every hour
    },
    "send-analytics-to-service": {
        "task": "apps.monitoring.tasks.send_analytics_to_service",
        "schedule": 86400.0,  # Every 24 hours
    },
    "health-check": {
        "task": "apps.monitoring.tasks.health_check_task",
        "schedule": 300.0,  # Every 5 minutes
    },
}
