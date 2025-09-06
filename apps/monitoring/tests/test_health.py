"""
Tests for health check views and functionality.
"""

import time
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


class HealthCheckViewTest(TestCase):
    """Tests for health check endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.health_url = reverse("health_check")

    @patch("apps.monitoring.health.DatabaseHealthCheck")
    @patch("apps.monitoring.health.cache")
    def test_health_check_all_healthy(self, mock_cache, mock_db_health):
        """Test health check when all services are healthy."""
        # Mock healthy database
        mock_db_health.is_healthy.return_value = True

        # Mock healthy cache
        mock_cache.set.return_value = None
        mock_cache.get.return_value = "ok"

        response = self.client.get(self.health_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "healthy")
        self.assertEqual(response.data["services"]["database"], "healthy")
        self.assertEqual(response.data["services"]["cache"], "healthy")
        self.assertIn("timestamp", response.data)
        self.assertIn("version", response.data)
        self.assertNotIn("errors", response.data)

    @patch("apps.monitoring.health.DatabaseHealthCheck")
    @patch("apps.monitoring.health.cache")
    def test_health_check_database_unhealthy(self, mock_cache, mock_db_health):
        """Test health check when database is unhealthy."""
        # Mock unhealthy database
        mock_db_health.is_healthy.return_value = False

        # Mock healthy cache
        mock_cache.set.return_value = None
        mock_cache.get.return_value = "ok"

        response = self.client.get(self.health_url)

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["status"], "unhealthy")
        self.assertEqual(response.data["services"]["database"], "unhealthy")
        self.assertEqual(response.data["services"]["cache"], "healthy")
        self.assertIn("errors", response.data)
        self.assertIn("Database: Connection failed after retries", response.data["errors"])

    @patch("apps.monitoring.health.DatabaseHealthCheck")
    @patch("apps.monitoring.health.cache")
    def test_health_check_database_exception(self, mock_cache, mock_db_health):
        """Test health check when database check raises exception."""
        # Mock database exception
        mock_db_health.is_healthy.side_effect = Exception("Database connection error")

        # Mock healthy cache
        mock_cache.set.return_value = None
        mock_cache.get.return_value = "ok"

        response = self.client.get(self.health_url)

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["status"], "unhealthy")
        self.assertEqual(response.data["services"]["database"], "unhealthy")
        self.assertEqual(response.data["services"]["cache"], "healthy")
        self.assertIn("errors", response.data)
        self.assertIn("Database: Database connection error", response.data["errors"])

    @patch("apps.monitoring.health.DatabaseHealthCheck")
    @patch("apps.monitoring.health.cache")
    def test_health_check_cache_unhealthy(self, mock_cache, mock_db_health):
        """Test health check when cache is unhealthy."""
        # Mock healthy database
        mock_db_health.is_healthy.return_value = True

        # Mock cache that fails to retrieve value
        mock_cache.set.return_value = None
        mock_cache.get.return_value = None  # Cache retrieval fails

        response = self.client.get(self.health_url)

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["status"], "unhealthy")
        self.assertEqual(response.data["services"]["database"], "healthy")
        self.assertEqual(response.data["services"]["cache"], "unhealthy")
        self.assertIn("errors", response.data)
        self.assertIn("Cache:", response.data["errors"][0])

    @patch("apps.monitoring.health.DatabaseHealthCheck")
    @patch("apps.monitoring.health.cache")
    def test_health_check_cache_exception(self, mock_cache, mock_db_health):
        """Test health check when cache check raises exception."""
        # Mock healthy database
        mock_db_health.is_healthy.return_value = True

        # Mock cache exception
        mock_cache.set.side_effect = Exception("Redis connection error")

        response = self.client.get(self.health_url)

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["status"], "unhealthy")
        self.assertEqual(response.data["services"]["database"], "healthy")
        self.assertEqual(response.data["services"]["cache"], "unhealthy")
        self.assertIn("errors", response.data)
        self.assertIn("Cache: Redis connection error", response.data["errors"])

    @patch("apps.monitoring.health.DatabaseHealthCheck")
    @patch("apps.monitoring.health.cache")
    def test_health_check_all_unhealthy(self, mock_cache, mock_db_health):
        """Test health check when all services are unhealthy."""
        # Mock unhealthy database
        mock_db_health.is_healthy.return_value = False

        # Mock unhealthy cache
        mock_cache.set.side_effect = Exception("Cache error")

        response = self.client.get(self.health_url)

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["status"], "unhealthy")
        self.assertEqual(response.data["services"]["database"], "unhealthy")
        self.assertEqual(response.data["services"]["cache"], "unhealthy")
        self.assertIn("errors", response.data)
        self.assertEqual(len(response.data["errors"]), 2)

    @patch("apps.monitoring.health.DatabaseHealthCheck")
    @patch("apps.monitoring.health.cache")
    @patch("apps.monitoring.health.settings")
    def test_health_check_response_format(self, mock_settings, mock_cache, mock_db_health):
        """Test health check response format and fields."""
        # Mock healthy services
        mock_db_health.is_healthy.return_value = True
        mock_cache.set.return_value = None
        mock_cache.get.return_value = "ok"
        mock_settings.VERSION = "2.0.0"

        response = self.client.get(self.health_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check required fields
        self.assertIn("status", response.data)
        self.assertIn("timestamp", response.data)
        self.assertIn("version", response.data)
        self.assertIn("services", response.data)

        # Check services structure
        self.assertIn("database", response.data["services"])
        self.assertIn("cache", response.data["services"])

        # Check version is correctly set
        self.assertEqual(response.data["version"], "2.0.0")

        # Check timestamp format (ISO format)
        timestamp = response.data["timestamp"]
        self.assertRegex(timestamp, r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")

    @patch("apps.monitoring.health.DatabaseHealthCheck")
    @patch("apps.monitoring.health.cache")
    @patch("apps.monitoring.health.settings")
    def test_health_check_default_version(self, mock_settings, mock_cache, mock_db_health):
        """Test health check with default version when VERSION setting is missing."""
        # Mock healthy services
        mock_db_health.is_healthy.return_value = True
        mock_cache.set.return_value = None
        mock_cache.get.return_value = "ok"

        # Mock settings without VERSION attribute
        mock_settings.VERSION = None

        def getattr_side_effect(obj, name, default=None):
            if name == "VERSION":
                return default
            return getattr(obj, name, default)

        with patch("apps.monitoring.health.getattr", side_effect=getattr_side_effect):
            response = self.client.get(self.health_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["version"], "1.0.0")  # Default version

    def test_health_check_endpoint_accessibility(self):
        """Test that health check endpoint is accessible without authentication."""
        # This should work without any authentication
        response = self.client.get(self.health_url)

        # Should not return 401/403, though it might return 503 if services are unhealthy
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE])


class ReadinessCheckViewTest(TestCase):
    """Tests for readiness check endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.readiness_url = reverse("readiness_check")

    @patch("apps.monitoring.health.DatabaseHealthCheck")
    def test_readiness_check_healthy(self, mock_db_health):
        """Test readiness check when database is healthy."""
        mock_db_health.is_healthy.return_value = True

        response = self.client.get(self.readiness_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ready")

        # Verify it uses cache=True for performance
        mock_db_health.is_healthy.assert_called_once_with(use_cache=True)

    @patch("apps.monitoring.health.DatabaseHealthCheck")
    def test_readiness_check_unhealthy(self, mock_db_health):
        """Test readiness check when database is unhealthy."""
        mock_db_health.is_healthy.return_value = False

        response = self.client.get(self.readiness_url)

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["status"], "not ready")

    @patch("apps.monitoring.health.DatabaseHealthCheck")
    def test_readiness_check_exception(self, mock_db_health):
        """Test readiness check when database check raises exception."""
        mock_db_health.is_healthy.side_effect = Exception("Database error")

        response = self.client.get(self.readiness_url)

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["status"], "not ready")

    def test_readiness_check_endpoint_accessibility(self):
        """Test that readiness check endpoint is accessible without authentication."""
        response = self.client.get(self.readiness_url)

        # Should not return 401/403
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE])


class LivenessCheckViewTest(TestCase):
    """Tests for liveness check endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.liveness_url = reverse("liveness_check")

    def test_liveness_check_always_healthy(self):
        """Test that liveness check always returns healthy."""
        response = self.client.get(self.liveness_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "alive")

    def test_liveness_check_endpoint_accessibility(self):
        """Test that liveness check endpoint is accessible without authentication."""
        response = self.client.get(self.liveness_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_liveness_check_multiple_requests(self):
        """Test that liveness check consistently returns the same response."""
        for _ in range(5):
            response = self.client.get(self.liveness_url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data["status"], "alive")


class HealthCheckCacheRetryTest(TestCase):
    """Tests for cache retry logic in health check."""

    def setUp(self):
        self.client = APIClient()
        self.health_url = reverse("health_check")

    @patch("apps.monitoring.health.DatabaseHealthCheck")
    @patch("apps.monitoring.health.cache")
    def test_cache_retry_logic_exists(self, mock_cache, mock_db_health):
        """Test that cache check has retry logic (even if it ultimately fails)."""
        # Mock healthy database
        mock_db_health.is_healthy.return_value = True

        # Mock cache that always fails to test retry behavior
        mock_cache.set.return_value = None
        mock_cache.get.return_value = None  # Always fails

        response = self.client.get(self.health_url)

        # The retry decorator is applied, so this tests the retry mechanism exists
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["services"]["cache"], "unhealthy")

        # Verify cache.get was called (retry mechanism would call it multiple times)
        self.assertTrue(mock_cache.get.called)

    @patch("apps.monitoring.health.DatabaseHealthCheck")
    @patch("apps.monitoring.health.cache")
    def test_cache_retry_final_failure(self, mock_cache, mock_db_health):
        """Test cache check fails after all retries exhausted."""
        # Mock healthy database
        mock_db_health.is_healthy.return_value = True

        # Mock cache that always fails
        mock_cache.set.return_value = None
        mock_cache.get.return_value = None  # Always fails

        response = self.client.get(self.health_url)

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["services"]["cache"], "unhealthy")


class HealthCheckTimestampTest(TestCase):
    """Tests for timestamp functionality in health check."""

    def setUp(self):
        self.client = APIClient()
        self.health_url = reverse("health_check")

    @patch("apps.monitoring.health.DatabaseHealthCheck")
    @patch("apps.monitoring.health.cache")
    @patch("apps.monitoring.health.time")
    def test_timestamp_format(self, mock_time, mock_cache, mock_db_health):
        """Test timestamp format in health check response."""
        # Mock healthy services
        mock_db_health.is_healthy.return_value = True
        mock_cache.set.return_value = None
        mock_cache.get.return_value = "ok"

        # Mock specific timestamp
        mock_time.strftime.return_value = "2024-01-15T10:30:45Z"
        mock_time.gmtime.return_value = time.struct_time((2024, 1, 15, 10, 30, 45, 0, 15, 0))

        response = self.client.get(self.health_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["timestamp"], "2024-01-15T10:30:45Z")

        # Verify strftime was called with correct format
        mock_time.strftime.assert_called_once_with("%Y-%m-%dT%H:%M:%SZ", mock_time.gmtime.return_value)

    @patch("apps.monitoring.health.DatabaseHealthCheck")
    @patch("apps.monitoring.health.cache")
    def test_timestamp_format_valid(self, mock_cache, mock_db_health):
        """Test that timestamp is in valid ISO format."""
        # Mock healthy services
        mock_db_health.is_healthy.return_value = True
        mock_cache.set.return_value = None
        mock_cache.get.return_value = "ok"

        response = self.client.get(self.health_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Just test that timestamp is in correct format, not exact timing
        timestamp_str = response.data["timestamp"]

        # Verify it matches the expected format
        self.assertRegex(timestamp_str, r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")

        # Verify it can be parsed as a valid time
        try:
            time.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            self.fail(f"Timestamp '{timestamp_str}' is not in expected format")


class HealthCheckErrorMessagesTest(TestCase):
    """Tests for error message handling in health checks."""

    def setUp(self):
        self.client = APIClient()
        self.health_url = reverse("health_check")

    @patch("apps.monitoring.health.DatabaseHealthCheck")
    @patch("apps.monitoring.health.cache")
    def test_error_message_database_specific(self, mock_cache, mock_db_health):
        """Test specific error messages for database failures."""
        # Mock database exception with specific message
        mock_db_health.is_healthy.side_effect = Exception("Connection timeout after 30 seconds")

        # Mock healthy cache
        mock_cache.set.return_value = None
        mock_cache.get.return_value = "ok"

        response = self.client.get(self.health_url)

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn("errors", response.data)
        self.assertIn("Database: Connection timeout after 30 seconds", response.data["errors"])

    @patch("apps.monitoring.health.DatabaseHealthCheck")
    @patch("apps.monitoring.health.cache")
    def test_error_message_cache_specific(self, mock_cache, mock_db_health):
        """Test specific error messages for cache failures."""
        # Mock healthy database
        mock_db_health.is_healthy.return_value = True

        # Mock cache exception with specific message
        mock_cache.set.side_effect = Exception("Redis server not available")

        response = self.client.get(self.health_url)

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn("errors", response.data)
        self.assertIn("Cache: Redis server not available", response.data["errors"])

    @patch("apps.monitoring.health.DatabaseHealthCheck")
    @patch("apps.monitoring.health.cache")
    def test_multiple_error_messages(self, mock_cache, mock_db_health):
        """Test handling of multiple error messages."""
        # Mock database exception
        mock_db_health.is_healthy.side_effect = Exception("Database error")

        # Mock cache exception
        mock_cache.set.side_effect = Exception("Cache error")

        response = self.client.get(self.health_url)

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn("errors", response.data)
        self.assertEqual(len(response.data["errors"]), 2)

        error_messages = response.data["errors"]
        self.assertTrue(any("Database:" in msg for msg in error_messages))
        self.assertTrue(any("Cache:" in msg for msg in error_messages))


class HealthCheckEdgeCasesTest(TestCase):
    """Tests for edge cases in health check functionality."""

    def setUp(self):
        self.client = APIClient()
        self.health_url = reverse("health_check")

    @patch("apps.monitoring.health.DatabaseHealthCheck")
    @patch("apps.monitoring.health.cache")
    def test_cache_partial_failure(self, mock_cache, mock_db_health):
        """Test cache check when set succeeds but get fails."""
        # Mock healthy database
        mock_db_health.is_healthy.return_value = True

        # Mock cache where set works but get returns wrong value
        mock_cache.set.return_value = None
        mock_cache.get.return_value = "wrong_value"

        response = self.client.get(self.health_url)

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["services"]["cache"], "unhealthy")

    @patch("apps.monitoring.health.DatabaseHealthCheck")
    @patch("apps.monitoring.health.cache")
    def test_none_values_handling(self, mock_cache, mock_db_health):
        """Test handling of None return values."""
        # Mock database returning None (edge case)
        mock_db_health.is_healthy.return_value = None

        # Mock cache returning None
        mock_cache.set.return_value = None
        mock_cache.get.return_value = None

        response = self.client.get(self.health_url)

        # None should be treated as unhealthy
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["services"]["database"], "unhealthy")
        self.assertEqual(response.data["services"]["cache"], "unhealthy")
