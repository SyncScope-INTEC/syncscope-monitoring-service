"""
Tests for exceptions module.
"""

from unittest.mock import MagicMock, Mock, patch

from django.db import InterfaceError, OperationalError
from django.test import RequestFactory, TestCase
from rest_framework import status
from rest_framework.response import Response

from apps.monitoring.exceptions import (
    DatabaseConnectionError,
    ErrorResponse,
    InvalidSessionStateError,
    MonitoringServiceError,
    RateLimitExceededError,
    SessionNotFoundError,
    ValidationError,
    custom_exception_handler,
    get_error_code_from_status,
    get_error_message_from_data,
    get_timestamp,
)


class ExceptionsClassesTest(TestCase):
    """Test custom exception classes."""

    def test_monitoring_service_error(self):
        """Test base MonitoringServiceError."""
        exc = MonitoringServiceError("Test error")
        self.assertEqual(str(exc), "Test error")
        self.assertIsInstance(exc, Exception)

    def test_database_connection_error(self):
        """Test DatabaseConnectionError."""
        exc = DatabaseConnectionError("Database connection failed")
        self.assertEqual(str(exc), "Database connection failed")
        self.assertIsInstance(exc, MonitoringServiceError)

    def test_session_not_found_error(self):
        """Test SessionNotFoundError."""
        exc = SessionNotFoundError("Session not found")
        self.assertEqual(str(exc), "Session not found")
        self.assertIsInstance(exc, MonitoringServiceError)

    def test_invalid_session_state_error(self):
        """Test InvalidSessionStateError."""
        exc = InvalidSessionStateError("Invalid state")
        self.assertEqual(str(exc), "Invalid state")
        self.assertIsInstance(exc, MonitoringServiceError)

    def test_rate_limit_exceeded_error(self):
        """Test RateLimitExceededError."""
        exc = RateLimitExceededError("Rate limit exceeded")
        self.assertEqual(str(exc), "Rate limit exceeded")
        self.assertIsInstance(exc, MonitoringServiceError)

    def test_validation_error(self):
        """Test custom ValidationError."""
        exc = ValidationError("Validation failed")
        self.assertEqual(str(exc), "Validation failed")
        self.assertIsInstance(exc, MonitoringServiceError)


class CustomExceptionHandlerTest(TestCase):
    """Test custom exception handler."""

    def setUp(self):
        self.factory = RequestFactory()

    def create_context(self, request=None):
        """Create exception context."""
        if request is None:
            request = self.factory.get("/")
            request.request_id = "test-request-123"
        return {"request": request}

    @patch("apps.monitoring.exceptions.drf_exception_handler")
    def test_database_connection_error_handling(self, mock_drf_handler):
        """Test handling of database connection errors."""
        mock_drf_handler.return_value = None

        exc = DatabaseConnectionError("Database connection failed")
        context = self.create_context()

        response = custom_exception_handler(exc, context)

        self.assertIsInstance(response, Response)
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["error"], "database_error")
        self.assertEqual(response.data["request_id"], "test-request-123")

    @patch("apps.monitoring.exceptions.drf_exception_handler")
    def test_operational_error_handling(self, mock_drf_handler):
        """Test handling of OperationalError."""
        mock_drf_handler.return_value = None

        exc = OperationalError("Database operation failed")
        context = self.create_context()

        response = custom_exception_handler(exc, context)

        self.assertIsInstance(response, Response)
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["error"], "database_error")

    @patch("apps.monitoring.exceptions.drf_exception_handler")
    def test_interface_error_handling(self, mock_drf_handler):
        """Test handling of InterfaceError."""
        mock_drf_handler.return_value = None

        exc = InterfaceError("Database interface error")
        context = self.create_context()

        response = custom_exception_handler(exc, context)

        self.assertIsInstance(response, Response)
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    @patch("apps.monitoring.exceptions.drf_exception_handler")
    def test_session_not_found_error_handling(self, mock_drf_handler):
        """Test handling of SessionNotFoundError."""
        mock_drf_handler.return_value = None

        exc = SessionNotFoundError("Session not found")
        context = self.create_context()

        response = custom_exception_handler(exc, context)

        self.assertIsInstance(response, Response)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"], "session_not_found")
        self.assertEqual(response.data["details"], "Session not found")

    @patch("apps.monitoring.exceptions.drf_exception_handler")
    def test_invalid_session_state_error_handling(self, mock_drf_handler):
        """Test handling of InvalidSessionStateError."""
        mock_drf_handler.return_value = None

        exc = InvalidSessionStateError("Invalid session state")
        context = self.create_context()

        response = custom_exception_handler(exc, context)

        self.assertIsInstance(response, Response)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "invalid_session_state")

    @patch("apps.monitoring.exceptions.drf_exception_handler")
    def test_rate_limit_exceeded_error_handling(self, mock_drf_handler):
        """Test handling of RateLimitExceededError."""
        mock_drf_handler.return_value = None

        exc = RateLimitExceededError("Rate limit exceeded")
        context = self.create_context()

        response = custom_exception_handler(exc, context)

        self.assertIsInstance(response, Response)
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response.data["error"], "rate_limit_exceeded")

    @patch("apps.monitoring.exceptions.drf_exception_handler")
    def test_drf_response_enhancement_dict_data(self, mock_drf_handler):
        """Test enhancement of DRF response with dict data."""
        # Mock DRF response
        mock_response = Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        mock_drf_handler.return_value = mock_response

        exc = Exception("Generic error")
        context = self.create_context()

        response = custom_exception_handler(exc, context)

        self.assertIsInstance(response, Response)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error"], "not_found")
        self.assertIn("timestamp", response.data)

    @patch("apps.monitoring.exceptions.drf_exception_handler")
    def test_drf_response_enhancement_non_dict_data(self, mock_drf_handler):
        """Test enhancement of DRF response with non-dict data."""
        # Mock DRF response with string data
        mock_response = Response("String error", status=status.HTTP_400_BAD_REQUEST)
        mock_drf_handler.return_value = mock_response

        exc = Exception("Generic error")
        context = self.create_context()

        response = custom_exception_handler(exc, context)

        self.assertIsInstance(response, Response)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["message"], "String error")

    @patch("apps.monitoring.exceptions.drf_exception_handler")
    def test_context_without_request(self, mock_drf_handler):
        """Test handler with context that has no request."""
        mock_drf_handler.return_value = None

        exc = SessionNotFoundError("Session not found")
        context = {}  # No request

        response = custom_exception_handler(exc, context)

        self.assertIsInstance(response, Response)
        self.assertIsNone(response.data["request_id"])

    @patch("apps.monitoring.exceptions.drf_exception_handler")
    def test_request_without_request_id(self, mock_drf_handler):
        """Test handler with request that has no request_id."""
        mock_drf_handler.return_value = None

        exc = SessionNotFoundError("Session not found")
        request = self.factory.get("/")  # No request_id attribute
        context = {"request": request}

        response = custom_exception_handler(exc, context)

        self.assertIsInstance(response, Response)
        self.assertIsNone(response.data["request_id"])


class UtilityFunctionsTest(TestCase):
    """Test utility functions."""

    def test_get_timestamp(self):
        """Test get_timestamp function."""
        timestamp = get_timestamp()
        self.assertIsInstance(timestamp, str)
        # Basic format check - should be ISO format
        self.assertIn("T", timestamp)

    def test_get_error_code_from_status(self):
        """Test get_error_code_from_status function."""
        test_cases = [
            (400, "bad_request"),
            (401, "unauthorized"),
            (403, "forbidden"),
            (404, "not_found"),
            (429, "rate_limit_exceeded"),
            (500, "internal_server_error"),
            (503, "service_unavailable"),
            (999, "http_999"),  # Unknown status code
        ]

        for status_code, expected_code in test_cases:
            with self.subTest(status_code=status_code):
                result = get_error_code_from_status(status_code)
                self.assertEqual(result, expected_code)

    def test_get_error_message_from_data_detail_field(self):
        """Test get_error_message_from_data with detail field."""
        data = {"detail": "Detailed error message"}
        message = get_error_message_from_data(data)
        self.assertEqual(message, "Detailed error message")

    def test_get_error_message_from_data_list_detail(self):
        """Test get_error_message_from_data with list detail."""
        data = {"detail": ["First error", "Second error"]}
        message = get_error_message_from_data(data)
        self.assertEqual(message, "First error")

    def test_get_error_message_from_data_field_errors(self):
        """Test get_error_message_from_data with field errors."""
        data = {"name": ["This field is required"], "email": "Invalid email format"}
        message = get_error_message_from_data(data)
        # Should contain both field errors
        self.assertIn("name:", message)
        self.assertIn("email:", message)

    def test_get_error_message_from_data_non_field_errors(self):
        """Test get_error_message_from_data with non_field_errors."""
        data = {"non_field_errors": ["General validation error"]}
        message = get_error_message_from_data(data)
        self.assertEqual(message, "General validation error")

    def test_get_error_message_from_data_empty_dict(self):
        """Test get_error_message_from_data with empty dict."""
        data = {}
        message = get_error_message_from_data(data)
        self.assertEqual(message, "An error occurred")

    def test_get_error_message_from_data_non_dict(self):
        """Test get_error_message_from_data with non-dict input."""
        message = get_error_message_from_data("string error")
        self.assertEqual(message, "An error occurred")


class ErrorResponseTest(TestCase):
    """Test ErrorResponse utility class."""

    def test_create_basic_response(self):
        """Test basic error response creation."""
        response = ErrorResponse.create(
            error_code="test_error", message="Test message", status_code=status.HTTP_400_BAD_REQUEST
        )

        self.assertIsInstance(response, Response)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "test_error")
        self.assertEqual(response.data["message"], "Test message")
        self.assertEqual(response.data["status"], "error")
        self.assertIn("timestamp", response.data)

    def test_create_with_details_and_request_id(self):
        """Test error response with details and request ID."""
        response = ErrorResponse.create(
            error_code="test_error", message="Test message", details={"field": "error details"}, request_id="request-123"
        )

        self.assertEqual(response.data["details"], {"field": "error details"})
        self.assertEqual(response.data["request_id"], "request-123")

    def test_validation_error(self):
        """Test validation error response."""
        errors = {"name": ["Required field"], "email": ["Invalid format"]}
        response = ErrorResponse.validation_error(errors, request_id="req-123")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "validation_error")
        self.assertEqual(response.data["message"], "Validation failed")
        self.assertEqual(response.data["details"], errors)
        self.assertEqual(response.data["request_id"], "req-123")

    def test_not_found_default(self):
        """Test not found error response with default resource name."""
        response = ErrorResponse.not_found()

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"], "not_found")
        self.assertEqual(response.data["message"], "Resource not found")

    def test_not_found_custom_resource(self):
        """Test not found error response with custom resource name."""
        response = ErrorResponse.not_found("Session", request_id="req-123")

        self.assertEqual(response.data["message"], "Session not found")
        self.assertEqual(response.data["request_id"], "req-123")

    def test_permission_denied_default(self):
        """Test permission denied error response with default message."""
        response = ErrorResponse.permission_denied()

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["error"], "permission_denied")
        self.assertEqual(response.data["message"], "Permission denied")

    def test_permission_denied_custom_message(self):
        """Test permission denied error response with custom message."""
        response = ErrorResponse.permission_denied("Access denied to this resource")

        self.assertEqual(response.data["message"], "Access denied to this resource")

    def test_service_unavailable_default(self):
        """Test service unavailable error response with default message."""
        response = ErrorResponse.service_unavailable()

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["error"], "service_unavailable")
        self.assertEqual(response.data["message"], "Service temporarily unavailable")

    def test_service_unavailable_custom_message(self):
        """Test service unavailable error response with custom message."""
        response = ErrorResponse.service_unavailable("Database maintenance in progress", "req-123")

        self.assertEqual(response.data["message"], "Database maintenance in progress")
        self.assertEqual(response.data["request_id"], "req-123")
