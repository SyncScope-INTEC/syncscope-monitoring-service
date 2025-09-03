"""
Redis client utilities for monitoring service.
"""

import logging

import redis
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class RedisClient:
    def __init__(self):
        self.redis_client = redis.from_url(settings.CACHES["default"]["LOCATION"])

    def set_session_data(self, session_id, data, timeout=300):
        """Store session data in Redis with timeout."""
        try:
            key = f"session:{session_id}"
            return cache.set(key, data, timeout)
        except Exception as e:
            logger.error(f"Failed to set session data for {session_id}: {e}")
            return False

    def get_session_data(self, session_id):
        """Retrieve session data from Redis."""
        try:
            key = f"session:{session_id}"
            return cache.get(key)
        except Exception as e:
            logger.error(f"Failed to get session data for {session_id}: {e}")
            return None

    def delete_session_data(self, session_id):
        """Delete session data from Redis."""
        try:
            key = f"session:{session_id}"
            return cache.delete(key)
        except Exception as e:
            logger.error(f"Failed to delete session data for {session_id}: {e}")
            return False

    def set_metrics_cache(self, user_id, metrics, timeout=3600):
        """Cache user metrics for performance."""
        try:
            key = f"metrics:{user_id}"
            return cache.set(key, metrics, timeout)
        except Exception as e:
            logger.error(f"Failed to cache metrics for user {user_id}: {e}")
            return False

    def get_metrics_cache(self, user_id):
        """Retrieve cached metrics."""
        try:
            key = f"metrics:{user_id}"
            return cache.get(key)
        except Exception as e:
            logger.error(f"Failed to get cached metrics for user {user_id}: {e}")
            return None
