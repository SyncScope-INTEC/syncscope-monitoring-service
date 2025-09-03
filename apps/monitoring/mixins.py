"""
Mixins for monitoring service models and views.
"""

import logging
import time

from django.core.cache import cache

logger = logging.getLogger(__name__)


class CacheHealthCheck:
    """
    Utility class for monitoring Redis/cache health.
    """

    CACHE_HEALTH_KEY = "cache_health_test"

    @classmethod
    def is_healthy(cls):
        """Check if cache is healthy."""
        try:
            # Try to set and get a test value
            test_value = "health_check"
            cache.set(cls.CACHE_HEALTH_KEY, test_value, 10)
            retrieved_value = cache.get(cls.CACHE_HEALTH_KEY)

            if retrieved_value == test_value:
                cache.delete(cls.CACHE_HEALTH_KEY)
                return True
            return False
        except Exception as e:
            logger.error(f"Cache health check failed: {e}")
            return False


class PerformanceMonitoringMixin:
    """
    Mixin to add performance monitoring to views.
    """

    def dispatch(self, request, *args, **kwargs):
        """Add performance monitoring to request handling."""
        start_time = time.time()

        # Add request ID if not present
        if not hasattr(request, "request_id"):
            import uuid

            request.request_id = str(uuid.uuid4())[:8]

        try:
            response = super().dispatch(request, *args, **kwargs)

            # Log performance metrics
            duration = (time.time() - start_time) * 1000
            if duration > 1000:  # Log slow requests (>1s)
                logger.warning(
                    f"Slow request detected: {request.method} {request.path} "
                    f"took {duration:.2f}ms (request_id: {request.request_id})"
                )

            # Add performance headers
            response["X-Response-Time"] = f"{duration:.2f}ms"
            response["X-Request-ID"] = request.request_id

            return response

        except Exception as e:
            duration = (time.time() - start_time) * 1000
            logger.error(
                f"Request failed after {duration:.2f}ms: {request.method} {request.path} "
                f"(request_id: {request.request_id}) - {e}"
            )
            raise
