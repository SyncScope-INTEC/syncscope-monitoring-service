"""
Custom decorators for monitoring service including rate limiting.
"""

from django_ratelimit.decorators import ratelimit
from django.conf import settings
from functools import wraps
import logging

logger = logging.getLogger(__name__)


def monitoring_ratelimit(group=None, key=None, rate=None, method=['POST'], block=True):
    """
    Rate limiting decorator for monitoring endpoints.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not settings.RATELIMIT_ENABLE:
                return func(*args, **kwargs)
            
            # Apply rate limiting
            rate_limited_func = ratelimit(
                group=group or func.__name__,
                key=key or 'user',
                rate=rate or '100/h',
                method=method,
                block=block
            )(func)
            
            return rate_limited_func(*args, **kwargs)
        return wrapper
    return decorator


# Predefined rate limits for different endpoint types
def session_ratelimit(func):
    """Rate limit for session endpoints - more restrictive."""
    return monitoring_ratelimit(
        group='sessions',
        key='user',
        rate='50/h',
        method=['POST', 'GET']
    )(func)


def activity_ratelimit(func):
    """Rate limit for activity endpoints - allows bulk uploads."""
    return monitoring_ratelimit(
        group='activities',
        key='user',
        rate='200/h',
        method=['POST']
    )(func)


def metrics_ratelimit(func):
    """Rate limit for metrics endpoints."""
    return monitoring_ratelimit(
        group='metrics',
        key='user',
        rate='500/h',
        method=['POST']
    )(func)


def git_events_ratelimit(func):
    """Rate limit for git events - moderate usage expected."""
    return monitoring_ratelimit(
        group='git_events',
        key='user',
        rate='100/h',
        method=['POST']
    )(func)


def health_ratelimit(func):
    """Rate limit for health checks - very permissive."""
    return monitoring_ratelimit(
        group='health',
        key='ip',
        rate='1000/h',
        method=['GET'],
        block=False  # Don't block health checks
    )(func)