"""
Tests for mixins module.
"""

import time
import uuid
from unittest.mock import MagicMock, Mock, patch

from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.views import View

from apps.monitoring.mixins import CacheHealthCheck, PerformanceMonitoringMixin


class CacheHealthCheckTest(TestCase):
    """Tests for CacheHealthCheck class."""

    def setUp(self):
        """Set up test fixtures."""
        cache.clear()

    def tearDown(self):
        """Clean up after each test."""
        cache.clear()

    def test_cache_health_key_constant(self):
        """Test that CACHE_HEALTH_KEY is properly defined."""
        self.assertEqual(CacheHealthCheck.CACHE_HEALTH_KEY, "cache_health_test")

    def test_is_healthy_success(self):
        """Test successful cache health check."""
        result = CacheHealthCheck.is_healthy()

        self.assertTrue(result)

        # Verify cleanup - key should be deleted after successful test
        cached_value = cache.get(CacheHealthCheck.CACHE_HEALTH_KEY)
        self.assertIsNone(cached_value)

    @patch("apps.monitoring.mixins.cache")
    def test_is_healthy_cache_set_failure(self, mock_cache):
        """Test cache health check when cache.set fails."""
        mock_cache.set.side_effect = Exception("Cache connection failed")

        result = CacheHealthCheck.is_healthy()

        self.assertFalse(result)

    @patch("apps.monitoring.mixins.cache")
    def test_is_healthy_cache_get_failure(self, mock_cache):
        """Test cache health check when cache.get fails."""
        mock_cache.set.return_value = True
        mock_cache.get.side_effect = Exception("Cache read failed")

        result = CacheHealthCheck.is_healthy()

        self.assertFalse(result)

    @patch("apps.monitoring.mixins.cache")
    def test_is_healthy_cache_delete_failure(self, mock_cache):
        """Test cache health check when cache.delete fails but test still passes."""
        mock_cache.set.return_value = True
        mock_cache.get.return_value = "health_check"
        mock_cache.delete.side_effect = Exception("Cache delete failed")

        # Should return False because any exception fails the health check
        result = CacheHealthCheck.is_healthy()

        self.assertFalse(result)

    @patch("apps.monitoring.mixins.cache")
    def test_is_healthy_value_mismatch(self, mock_cache):
        """Test cache health check when retrieved value doesn't match."""
        mock_cache.set.return_value = True
        mock_cache.get.return_value = "wrong_value"

        result = CacheHealthCheck.is_healthy()

        self.assertFalse(result)

    @patch("apps.monitoring.mixins.cache")
    def test_is_healthy_get_returns_none(self, mock_cache):
        """Test cache health check when get returns None."""
        mock_cache.set.return_value = True
        mock_cache.get.return_value = None

        result = CacheHealthCheck.is_healthy()

        self.assertFalse(result)

    @patch("apps.monitoring.mixins.cache")
    def test_cache_operations_called_correctly(self, mock_cache):
        """Test that cache operations are called with correct parameters."""
        mock_cache.set.return_value = True
        mock_cache.get.return_value = "health_check"
        mock_cache.delete.return_value = True

        CacheHealthCheck.is_healthy()

        # Verify correct method calls
        mock_cache.set.assert_called_once_with("cache_health_test", "health_check", 10)
        mock_cache.get.assert_called_once_with("cache_health_test")
        mock_cache.delete.assert_called_once_with("cache_health_test")

    @patch("apps.monitoring.mixins.logger")
    @patch("apps.monitoring.mixins.cache")
    def test_error_logging(self, mock_cache, mock_logger):
        """Test that cache errors are properly logged."""
        mock_cache.set.side_effect = Exception("Cache error")

        CacheHealthCheck.is_healthy()

        mock_logger.error.assert_called_once()
        self.assertIn("Cache health check failed", str(mock_logger.error.call_args))


class PerformanceMonitoringMixinTest(TestCase):
    """Tests for PerformanceMonitoringMixin."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

        # Create a test view class that uses the mixin
        class TestView(PerformanceMonitoringMixin, View):
            def get(self, request):
                return HttpResponse("Success")

            def post(self, request):
                # Simulate slow operation
                time.sleep(0.1)
                return HttpResponse("Slow Success")

        self.view_class = TestView
        self.view = TestView()

    def test_dispatch_adds_request_id(self):
        """Test that dispatch adds request_id to request."""
        request = self.factory.get("/test/")

        # Mock the parent dispatch method
        with patch.object(View, "dispatch", return_value=HttpResponse("Success")) as mock_dispatch:
            response = self.view.dispatch(request)

            # Check that request_id was added
            self.assertTrue(hasattr(request, "request_id"))
            self.assertIsNotNone(request.request_id)
            self.assertEqual(len(request.request_id), 8)  # UUID first 8 chars

            # Check that parent dispatch was called
            mock_dispatch.assert_called_once_with(request)

    def test_dispatch_preserves_existing_request_id(self):
        """Test that dispatch preserves existing request_id."""
        request = self.factory.get("/test/")
        existing_id = "existing123"
        request.request_id = existing_id

        with patch.object(View, "dispatch", return_value=HttpResponse("Success")):
            self.view.dispatch(request)

            # Check that existing request_id was preserved
            self.assertEqual(request.request_id, existing_id)

    def test_dispatch_adds_performance_headers(self):
        """Test that dispatch adds performance headers to response."""
        request = self.factory.get("/test/")

        with patch.object(View, "dispatch", return_value=HttpResponse("Success")):
            response = self.view.dispatch(request)

            # Check response headers
            self.assertIn("X-Response-Time", response)
            self.assertIn("X-Request-ID", response)

            # Check header format
            response_time = response["X-Response-Time"]
            self.assertTrue(response_time.endswith("ms"))
            self.assertEqual(response["X-Request-ID"], request.request_id)

    def test_dispatch_measures_response_time(self):
        """Test that dispatch measures response time correctly."""
        request = self.factory.get("/test/")

        with patch.object(View, "dispatch") as mock_dispatch:
            # Simulate a slow response
            def slow_dispatch(*args, **kwargs):
                time.sleep(0.05)  # 50ms delay
                return HttpResponse("Slow Success")

            mock_dispatch.side_effect = slow_dispatch

            response = self.view.dispatch(request)

            # Check that response time is reasonable (should be >= 50ms)
            response_time_str = response["X-Response-Time"]
            response_time = float(response_time_str.replace("ms", ""))
            self.assertGreaterEqual(response_time, 45.0)  # Allow some variance

    @patch("apps.monitoring.mixins.logger")
    def test_dispatch_logs_slow_requests(self, mock_logger):
        """Test that slow requests are logged as warnings."""
        request = self.factory.get("/slow-endpoint/")

        with patch.object(View, "dispatch") as mock_dispatch:

            def very_slow_dispatch(*args, **kwargs):
                time.sleep(1.1)  # 1.1s delay (over threshold)
                return HttpResponse("Very Slow Success")

            mock_dispatch.side_effect = very_slow_dispatch

            self.view.dispatch(request)

            # Check that warning was logged
            mock_logger.warning.assert_called_once()
            log_message = str(mock_logger.warning.call_args)
            self.assertIn("Slow request detected", log_message)
            self.assertIn("GET /slow-endpoint/", log_message)
            self.assertIn("request_id:", log_message)

    @patch("apps.monitoring.mixins.logger")
    def test_dispatch_does_not_log_fast_requests(self, mock_logger):
        """Test that fast requests are not logged as warnings."""
        request = self.factory.get("/fast-endpoint/")

        with patch.object(View, "dispatch", return_value=HttpResponse("Fast Success")):
            self.view.dispatch(request)

            # Check that no warning was logged
            mock_logger.warning.assert_not_called()

    @patch("apps.monitoring.mixins.logger")
    def test_dispatch_handles_exceptions(self, mock_logger):
        """Test that dispatch properly handles and logs exceptions."""
        request = self.factory.post("/error-endpoint/")

        with patch.object(View, "dispatch") as mock_dispatch:
            mock_dispatch.side_effect = ValueError("Test error")

            # Exception should be re-raised
            with self.assertRaises(ValueError):
                self.view.dispatch(request)

            # Check that error was logged
            mock_logger.error.assert_called_once()
            log_message = str(mock_logger.error.call_args)
            self.assertIn("Request failed", log_message)
            self.assertIn("POST /error-endpoint/", log_message)
            self.assertIn("request_id:", log_message)
            self.assertIn("Test error", log_message)

    @patch("apps.monitoring.mixins.logger")
    def test_dispatch_logs_exception_timing(self, mock_logger):
        """Test that exception timing is logged correctly."""
        request = self.factory.get("/error-endpoint/")

        with patch.object(View, "dispatch") as mock_dispatch:

            def slow_error_dispatch(*args, **kwargs):
                time.sleep(0.05)  # 50ms delay
                raise RuntimeError("Slow error")

            mock_dispatch.side_effect = slow_error_dispatch

            with self.assertRaises(RuntimeError):
                self.view.dispatch(request)

            # Check that timing was included in error log
            log_message = str(mock_logger.error.call_args)
            self.assertIn("ms", log_message)

    def test_dispatch_uuid_generation(self):
        """Test that request_id is properly formatted UUID."""
        request = self.factory.get("/test/")

        with patch.object(View, "dispatch", return_value=HttpResponse("Success")):
            self.view.dispatch(request)

            # Check UUID format (8 characters, hex)
            request_id = request.request_id
            self.assertEqual(len(request_id), 8)
            self.assertTrue(all(c in "0123456789abcdef-" for c in request_id.lower()))

    def test_multiple_requests_different_ids(self):
        """Test that different requests get different IDs."""
        request1 = self.factory.get("/test1/")
        request2 = self.factory.get("/test2/")

        with patch.object(View, "dispatch", return_value=HttpResponse("Success")):
            self.view.dispatch(request1)
            self.view.dispatch(request2)

            # Check that IDs are different
            self.assertNotEqual(request1.request_id, request2.request_id)

    def test_inheritance_behavior(self):
        """Test that mixin works correctly with inheritance."""

        # Create a more complex inheritance hierarchy
        class BaseView(PerformanceMonitoringMixin, View):
            def dispatch(self, request, *args, **kwargs):
                return super().dispatch(request, *args, **kwargs)

        class SubView(BaseView):
            def get(self, request):
                return HttpResponse("Sub Success")

        view = SubView()
        request = self.factory.get("/sub/")

        response = view.dispatch(request)

        # Check that mixin functionality still works
        self.assertTrue(hasattr(request, "request_id"))
        self.assertIn("X-Response-Time", response)
        self.assertIn("X-Request-ID", response)

    @patch("apps.monitoring.mixins.uuid")
    def test_uuid_generation_mocked(self, mock_uuid):
        """Test UUID generation with mocked uuid."""
        mock_uuid_obj = Mock()
        mock_uuid_obj.__str__ = Mock(return_value="12345678-1234-5678-9abc-123456789abc")
        mock_uuid.uuid4.return_value = mock_uuid_obj

        request = self.factory.get("/test/")

        with patch.object(View, "dispatch", return_value=HttpResponse("Success")):
            self.view.dispatch(request)

            # Check that UUID was called and sliced correctly
            mock_uuid.uuid4.assert_called_once()
            self.assertEqual(request.request_id, "12345678")

    def test_response_time_header_format(self):
        """Test that response time header is properly formatted."""
        request = self.factory.get("/test/")

        with patch.object(View, "dispatch", return_value=HttpResponse("Success")):
            response = self.view.dispatch(request)

            response_time = response["X-Response-Time"]

            # Check format: number + "ms"
            self.assertTrue(response_time.endswith("ms"))
            time_value = response_time[:-2]  # Remove "ms"

            # Should be a valid float
            try:
                float(time_value)
            except ValueError:
                self.fail(f"Response time '{time_value}' is not a valid number")

    def test_performance_monitoring_integration(self):
        """Integration test for complete performance monitoring flow."""
        request = self.factory.post("/integration-test/")

        with patch.object(View, "dispatch") as mock_dispatch:

            def realistic_dispatch(*args, **kwargs):
                time.sleep(0.02)  # 20ms realistic delay
                return HttpResponse("Integration Success", status=201)

            mock_dispatch.side_effect = realistic_dispatch

            response = self.view.dispatch(request)

            # Check all aspects
            self.assertTrue(hasattr(request, "request_id"))
            self.assertIn("X-Response-Time", response)
            self.assertIn("X-Request-ID", response)
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.content.decode(), "Integration Success")

            # Verify timing is reasonable
            response_time = float(response["X-Response-Time"].replace("ms", ""))
            self.assertGreaterEqual(response_time, 15.0)  # At least 15ms
            self.assertLess(response_time, 100.0)  # But not too high
