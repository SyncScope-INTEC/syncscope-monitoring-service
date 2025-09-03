"""
Custom exceptions for monitoring service.
"""

import logging

from django.core.exceptions import ValidationError
from django.db import InterfaceError, OperationalError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


class MonitoringServiceError(Exception):
    """Base exception for monitoring service."""

    pass


class DatabaseConnectionError(MonitoringServiceError):
    """Raised when database connection fails."""

    pass


class SessionNotFoundError(MonitoringServiceError):
    """Raised when a session is not found."""

    pass


class InvalidSessionStateError(MonitoringServiceError):
    """Raised when a session is in an invalid state for the operation."""

    pass


class RateLimitExceededError(MonitoringServiceError):
    """Raised when rate limit is exceeded."""

    pass


class ValidationError(MonitoringServiceError):
    """Raised when validation fails."""

    pass


def custom_exception_handler(exc, context):
    """
    Custom exception handler with structured error responses.
    """
    # Get the standard error response first
    response = drf_exception_handler(exc, context)

    # Extract request information
    request = context.get("request")
    request_id = getattr(request, "request_id", None) if request else None

    # Database connection errors
    if isinstance(exc, (OperationalError, InterfaceError, DatabaseConnectionError)):
        logger.error(f"Database error in view: {exc}", extra={"request_id": request_id})

        custom_response_data = {
            "error": "database_error",
            "message": "Service temporarily unavailable due to database issues",
            "details": "Please try again in a few moments",
            "status": "error",
            "timestamp": get_timestamp(),
            "request_id": request_id,
        }
        return Response(custom_response_data, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    # Custom monitoring service errors
    if isinstance(exc, SessionNotFoundError):
        custom_response_data = {
            "error": "session_not_found",
            "message": "The specified session was not found",
            "details": str(exc) if str(exc) else "Session does not exist or has been deleted",
            "status": "error",
            "timestamp": get_timestamp(),
            "request_id": request_id,
        }
        return Response(custom_response_data, status=status.HTTP_404_NOT_FOUND)

    if isinstance(exc, InvalidSessionStateError):
        custom_response_data = {
            "error": "invalid_session_state",
            "message": "Invalid session state for this operation",
            "details": str(exc),
            "status": "error",
            "timestamp": get_timestamp(),
            "request_id": request_id,
        }
        return Response(custom_response_data, status=status.HTTP_400_BAD_REQUEST)

    if isinstance(exc, RateLimitExceededError):
        custom_response_data = {
            "error": "rate_limit_exceeded",
            "message": "Rate limit exceeded",
            "details": "Too many requests. Please slow down and try again later.",
            "status": "error",
            "timestamp": get_timestamp(),
            "request_id": request_id,
        }
        return Response(custom_response_data, status=status.HTTP_429_TOO_MANY_REQUESTS)

    # If we have a DRF response, enhance it with additional information
    if response is not None:
        # Extract error details from DRF response
        if hasattr(response, "data"):
            if isinstance(response.data, dict):
                # Enhance existing error response
                enhanced_data = {
                    "error": get_error_code_from_status(response.status_code),
                    "message": get_error_message_from_data(response.data),
                    "details": response.data,
                    "status": "error",
                    "timestamp": get_timestamp(),
                    "request_id": request_id,
                }
                response.data = enhanced_data
            else:
                # Handle non-dict responses
                enhanced_data = {
                    "error": get_error_code_from_status(response.status_code),
                    "message": str(response.data) if response.data else "An error occurred",
                    "details": response.data,
                    "status": "error",
                    "timestamp": get_timestamp(),
                    "request_id": request_id,
                }
                response.data = enhanced_data

    return response


def get_timestamp():
    """Get current timestamp in ISO format."""
    from django.utils import timezone

    return timezone.now().isoformat()


def get_error_code_from_status(status_code):
    """Convert HTTP status code to error code."""
    error_codes = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        405: "method_not_allowed",
        409: "conflict",
        422: "validation_error",
        429: "rate_limit_exceeded",
        500: "internal_server_error",
        502: "bad_gateway",
        503: "service_unavailable",
        504: "gateway_timeout",
    }
    return error_codes.get(status_code, f"http_{status_code}")


def get_error_message_from_data(data):
    """Extract error message from DRF error data."""
    if isinstance(data, dict):
        # Look for common error message fields
        for field in ["detail", "message", "error", "non_field_errors"]:
            if field in data:
                error_value = data[field]
                if isinstance(error_value, list) and error_value:
                    return str(error_value[0])
                elif isinstance(error_value, str):
                    return error_value

        # If no standard message field, try to construct from field errors
        field_errors = []
        for field, errors in data.items():
            if isinstance(errors, list):
                field_errors.append(f"{field}: {', '.join(str(e) for e in errors)}")
            else:
                field_errors.append(f"{field}: {errors}")

        if field_errors:
            return "; ".join(field_errors)

    return "An error occurred"


class ErrorResponse:
    """Utility class for creating standardized error responses."""

    @staticmethod
    def create(error_code, message, details=None, status_code=400, request_id=None):
        """Create a standardized error response."""
        response_data = {"error": error_code, "message": message, "status": "error", "timestamp": get_timestamp()}

        if details:
            response_data["details"] = details

        if request_id:
            response_data["request_id"] = request_id

        return Response(response_data, status=status_code)

    @staticmethod
    def validation_error(errors, request_id=None):
        """Create a validation error response."""
        return ErrorResponse.create(
            error_code="validation_error",
            message="Validation failed",
            details=errors,
            status_code=status.HTTP_400_BAD_REQUEST,
            request_id=request_id,
        )

    @staticmethod
    def not_found(resource_name="Resource", request_id=None):
        """Create a not found error response."""
        return ErrorResponse.create(
            error_code="not_found",
            message=f"{resource_name} not found",
            status_code=status.HTTP_404_NOT_FOUND,
            request_id=request_id,
        )

    @staticmethod
    def permission_denied(message="Permission denied", request_id=None):
        """Create a permission denied error response."""
        return ErrorResponse.create(
            error_code="permission_denied", message=message, status_code=status.HTTP_403_FORBIDDEN, request_id=request_id
        )

    @staticmethod
    def service_unavailable(message="Service temporarily unavailable", request_id=None):
        """Create a service unavailable error response."""
        return ErrorResponse.create(
            error_code="service_unavailable",
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            request_id=request_id,
        )
