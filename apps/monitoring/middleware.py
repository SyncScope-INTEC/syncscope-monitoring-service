"""
Custom middleware for monitoring service.
"""

import logging
import time
import uuid

from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(MiddlewareMixin):
    """
    Middleware to log API requests with structured logging.
    """

    def process_request(self, request):
        request.start_time = time.time()
        request.request_id = str(uuid.uuid4())[:8]

        # Skip logging for health checks and static files
        if request.path.startswith(("/health/", "/static/", "/media/")):
            return None

        logger.info(
            f"API Request Started: {request.method} {request.path}",
            extra={
                "request_id": request.request_id,
                "method": request.method,
                "path": request.path,
                "remote_addr": self._get_client_ip(request),
                "user_agent": request.META.get("HTTP_USER_AGENT", ""),
            },
        )

    def process_response(self, request, response):
        if hasattr(request, "start_time"):
            duration = (time.time() - request.start_time) * 1000  # Convert to ms

            # Skip logging for health checks and static files
            if not request.path.startswith(("/health/", "/static/", "/media/")):
                logger.info(
                    f"API Request Completed: {request.method} {request.path}",
                    extra={
                        "request_id": getattr(request, "request_id", "unknown"),
                        "method": request.method,
                        "path": request.path,
                        "status_code": response.status_code,
                        "duration": round(duration, 2),
                        "response_size": len(response.content) if hasattr(response, "content") else 0,
                    },
                )

        return response

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")


class CORSPreflightMiddleware(MiddlewareMixin):
    """
    Custom CORS preflight middleware for optimization.
    """

    def process_request(self, request):
        if request.method == "OPTIONS":
            # Handle preflight requests quickly
            response = HttpResponse()
            response["Access-Control-Allow-Origin"] = request.META.get("HTTP_ORIGIN", "*")
            response["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response[
                "Access-Control-Allow-Headers"
            ] = "authorization, content-type, x-csrftoken, x-requested-with, x-service-token"
            response["Access-Control-Allow-Credentials"] = "true"
            response["Access-Control-Max-Age"] = "86400"  # 24 hours
            return response
        return None


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Add comprehensive security headers to responses.
    """

    def process_response(self, request, response):
        # Core security headers
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = "DENY"
        response["X-XSS-Protection"] = "1; mode=block"
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Feature policy / permissions policy
        response["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), " "payment=(), usb=(), bluetooth=(), magnetometer=(), gyroscope=()"
        )

        # HSTS for HTTPS requests
        if request.is_secure():
            response["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        # Content Security Policy for API and web interface
        if request.path == "/" or request.path.startswith("/admin/"):
            # Allow inline styles and scripts for main homepage and admin interface
            response["Content-Security-Policy"] = (
                "default-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "script-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "font-src 'self'; "
                "frame-ancestors 'none'; "
                "base-uri 'self'"
            )
        elif request.path.startswith("/api/docs/") or request.path.startswith("/api/redoc/"):
            # Allow external CDN resources for Swagger UI and ReDoc
            response["Content-Security-Policy"] = (
                "default-src 'self'; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: https://cdn.jsdelivr.net; "
                "font-src 'self' https://cdn.jsdelivr.net; "
                "connect-src 'self'; "
                "worker-src 'self' blob:; "
                "frame-ancestors 'none'; "
                "base-uri 'self'"
            )
        else:
            # Stricter CSP for API endpoints
            response["Content-Security-Policy"] = "default-src 'none'; " "frame-ancestors 'none'; " "base-uri 'none'"

        # API-specific headers
        response["X-Service"] = "syncscope-monitoring-service"
        response["X-Version"] = "1.0.0"

        # Add request ID if available
        if hasattr(request, "request_id"):
            response["X-Request-ID"] = request.request_id

        # Rate limiting headers (if available)
        if hasattr(request, "rate_limit_info"):
            info = request.rate_limit_info
            response["X-RateLimit-Limit"] = str(info.get("limit", ""))
            response["X-RateLimit-Remaining"] = str(info.get("remaining", ""))
            response["X-RateLimit-Reset"] = str(info.get("reset", ""))

        return response


class RateLimitHeadersMiddleware(MiddlewareMixin):
    """
    Add rate limiting headers to responses.
    """

    def process_response(self, request, response):
        # Add rate limiting information if available
        if hasattr(request, "limited"):
            response["X-RateLimit-Limited"] = "true"

        # These would typically come from the rate limiting backend
        # For now, we'll add placeholders that could be populated by the rate limiting system
        if not response.get("X-RateLimit-Limit"):
            response["X-RateLimit-Limit"] = "100"
        if not response.get("X-RateLimit-Remaining"):
            response["X-RateLimit-Remaining"] = "99"
        if not response.get("X-RateLimit-Reset"):
            response["X-RateLimit-Reset"] = str(int(time.time()) + 3600)

        return response
