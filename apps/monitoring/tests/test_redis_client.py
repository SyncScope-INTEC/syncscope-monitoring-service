"""
Tests for redis_client module.
"""

import uuid
from unittest.mock import MagicMock, Mock, patch

import redis
from django.core.cache import cache
from django.test import TestCase, override_settings

from apps.monitoring.redis_client import RedisClient


class RedisClientTest(TestCase):
    """Tests for RedisClient class."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = RedisClient()

    def tearDown(self):
        """Clean up after each test."""
        cache.clear()

    @override_settings(CACHES={"default": {"LOCATION": "redis://localhost:6379/1"}})
    @patch("redis.from_url")
    def test_init_success(self, mock_redis_from_url):
        """Test successful RedisClient initialization."""
        mock_redis_client = MagicMock()
        mock_redis_from_url.return_value = mock_redis_client

        client = RedisClient()

        self.assertIsNotNone(client.redis_client)
        mock_redis_from_url.assert_called_once_with("redis://localhost:6379/1")

    @override_settings(CACHES={"default": {"LOCATION": "redis://custom-host:6380/2"}})
    @patch("redis.from_url")
    def test_init_custom_location(self, mock_redis_from_url):
        """Test RedisClient initialization with custom Redis location."""
        mock_redis_client = MagicMock()
        mock_redis_from_url.return_value = mock_redis_client

        client = RedisClient()

        mock_redis_from_url.assert_called_once_with("redis://custom-host:6380/2")

    @patch("apps.monitoring.redis_client.cache")
    def test_set_session_data_success(self, mock_cache):
        """Test successful session data setting."""
        mock_cache.set.return_value = True

        session_id = str(uuid.uuid4())
        data = {"user_id": 1, "session_start": "2024-01-01T12:00:00Z"}

        result = self.client.set_session_data(session_id, data, timeout=600)

        self.assertTrue(result)
        mock_cache.set.assert_called_once_with(f"session:{session_id}", data, 600)

    @patch("apps.monitoring.redis_client.cache")
    def test_set_session_data_default_timeout(self, mock_cache):
        """Test session data setting with default timeout."""
        mock_cache.set.return_value = True

        session_id = str(uuid.uuid4())
        data = {"user_id": 1}

        result = self.client.set_session_data(session_id, data)

        self.assertTrue(result)
        mock_cache.set.assert_called_once_with(f"session:{session_id}", data, 300)

    @patch("apps.monitoring.redis_client.cache")
    def test_set_session_data_failure(self, mock_cache):
        """Test session data setting failure."""
        mock_cache.set.side_effect = Exception("Redis connection failed")

        session_id = str(uuid.uuid4())
        data = {"user_id": 1}

        result = self.client.set_session_data(session_id, data)

        self.assertFalse(result)

    @patch("apps.monitoring.redis_client.cache")
    def test_set_session_data_cache_returns_false(self, mock_cache):
        """Test session data setting when cache.set returns False."""
        mock_cache.set.return_value = False

        session_id = str(uuid.uuid4())
        data = {"user_id": 1}

        result = self.client.set_session_data(session_id, data)

        self.assertFalse(result)

    @patch("apps.monitoring.redis_client.cache")
    def test_get_session_data_success(self, mock_cache):
        """Test successful session data retrieval."""
        session_id = str(uuid.uuid4())
        expected_data = {"user_id": 1, "session_start": "2024-01-01T12:00:00Z"}
        mock_cache.get.return_value = expected_data

        result = self.client.get_session_data(session_id)

        self.assertEqual(result, expected_data)
        mock_cache.get.assert_called_once_with(f"session:{session_id}")

    @patch("apps.monitoring.redis_client.cache")
    def test_get_session_data_not_found(self, mock_cache):
        """Test session data retrieval when data not found."""
        mock_cache.get.return_value = None

        session_id = str(uuid.uuid4())

        result = self.client.get_session_data(session_id)

        self.assertIsNone(result)

    @patch("apps.monitoring.redis_client.cache")
    def test_get_session_data_exception(self, mock_cache):
        """Test session data retrieval with exception."""
        mock_cache.get.side_effect = Exception("Redis connection failed")

        session_id = str(uuid.uuid4())

        result = self.client.get_session_data(session_id)

        self.assertIsNone(result)

    @patch("apps.monitoring.redis_client.cache")
    def test_delete_session_data_success(self, mock_cache):
        """Test successful session data deletion."""
        mock_cache.delete.return_value = True

        session_id = str(uuid.uuid4())

        result = self.client.delete_session_data(session_id)

        self.assertTrue(result)
        mock_cache.delete.assert_called_once_with(f"session:{session_id}")

    @patch("apps.monitoring.redis_client.cache")
    def test_delete_session_data_not_found(self, mock_cache):
        """Test session data deletion when data not found."""
        mock_cache.delete.return_value = False  # Key didn't exist

        session_id = str(uuid.uuid4())

        result = self.client.delete_session_data(session_id)

        self.assertFalse(result)

    @patch("apps.monitoring.redis_client.cache")
    def test_delete_session_data_exception(self, mock_cache):
        """Test session data deletion with exception."""
        mock_cache.delete.side_effect = Exception("Redis connection failed")

        session_id = str(uuid.uuid4())

        result = self.client.delete_session_data(session_id)

        self.assertFalse(result)

    @patch("apps.monitoring.redis_client.cache")
    def test_set_metrics_cache_success(self, mock_cache):
        """Test successful metrics caching."""
        mock_cache.set.return_value = True

        user_id = 1
        metrics = {"total_lines": 1000, "files_modified": 5, "complexity": 15.5}

        result = self.client.set_metrics_cache(user_id, metrics, timeout=1800)

        self.assertTrue(result)
        mock_cache.set.assert_called_once_with(f"metrics:{user_id}", metrics, 1800)

    @patch("apps.monitoring.redis_client.cache")
    def test_set_metrics_cache_default_timeout(self, mock_cache):
        """Test metrics caching with default timeout."""
        mock_cache.set.return_value = True

        user_id = 1
        metrics = {"total_lines": 1000}

        result = self.client.set_metrics_cache(user_id, metrics)

        self.assertTrue(result)
        mock_cache.set.assert_called_once_with(f"metrics:{user_id}", metrics, 3600)

    @patch("apps.monitoring.redis_client.cache")
    def test_set_metrics_cache_failure(self, mock_cache):
        """Test metrics caching failure."""
        mock_cache.set.side_effect = Exception("Redis connection failed")

        user_id = 1
        metrics = {"total_lines": 1000}

        result = self.client.set_metrics_cache(user_id, metrics)

        self.assertFalse(result)

    @patch("apps.monitoring.redis_client.cache")
    def test_get_metrics_cache_success(self, mock_cache):
        """Test successful metrics retrieval from cache."""
        user_id = 1
        expected_metrics = {"total_lines": 1000, "files_modified": 5, "complexity": 15.5}
        mock_cache.get.return_value = expected_metrics

        result = self.client.get_metrics_cache(user_id)

        self.assertEqual(result, expected_metrics)
        mock_cache.get.assert_called_once_with(f"metrics:{user_id}")

    @patch("apps.monitoring.redis_client.cache")
    def test_get_metrics_cache_not_found(self, mock_cache):
        """Test metrics retrieval when not found in cache."""
        mock_cache.get.return_value = None

        user_id = 1

        result = self.client.get_metrics_cache(user_id)

        self.assertIsNone(result)

    @patch("apps.monitoring.redis_client.cache")
    def test_get_metrics_cache_exception(self, mock_cache):
        """Test metrics retrieval with exception."""
        mock_cache.get.side_effect = Exception("Redis connection failed")

        user_id = 1

        result = self.client.get_metrics_cache(user_id)

        self.assertIsNone(result)

    def test_session_key_format(self):
        """Test session key format consistency."""
        session_id = "test-session-id"
        expected_key = f"session:{session_id}"

        with patch("apps.monitoring.redis_client.cache") as mock_cache:
            self.client.set_session_data(session_id, {})
            self.client.get_session_data(session_id)
            self.client.delete_session_data(session_id)

            # Check that all calls used the same key format
            set_call = mock_cache.set.call_args[0][0]
            get_call = mock_cache.get.call_args[0][0]
            delete_call = mock_cache.delete.call_args[0][0]

            self.assertEqual(set_call, expected_key)
            self.assertEqual(get_call, expected_key)
            self.assertEqual(delete_call, expected_key)

    def test_metrics_key_format(self):
        """Test metrics key format consistency."""
        user_id = 123
        expected_key = f"metrics:{user_id}"

        with patch("apps.monitoring.redis_client.cache") as mock_cache:
            self.client.set_metrics_cache(user_id, {})
            self.client.get_metrics_cache(user_id)

            # Check that all calls used the same key format
            set_call = mock_cache.set.call_args[0][0]
            get_call = mock_cache.get.call_args[0][0]

            self.assertEqual(set_call, expected_key)
            self.assertEqual(get_call, expected_key)

    @patch("apps.monitoring.redis_client.logger")
    @patch("apps.monitoring.redis_client.cache")
    def test_error_logging(self, mock_cache, mock_logger):
        """Test that errors are properly logged."""
        mock_cache.set.side_effect = Exception("Redis error")
        mock_cache.get.side_effect = Exception("Redis error")
        mock_cache.delete.side_effect = Exception("Redis error")

        session_id = "test-session"
        user_id = 1

        # Test all methods that should log errors
        self.client.set_session_data(session_id, {})
        self.client.get_session_data(session_id)
        self.client.delete_session_data(session_id)
        self.client.set_metrics_cache(user_id, {})
        self.client.get_metrics_cache(user_id)

        # Verify error logging was called for each method
        self.assertEqual(mock_logger.error.call_count, 5)

        # Check log messages contain expected content
        log_calls = mock_logger.error.call_args_list
        self.assertIn("Failed to set session data", str(log_calls[0]))
        self.assertIn("Failed to get session data", str(log_calls[1]))
        self.assertIn("Failed to delete session data", str(log_calls[2]))
        self.assertIn("Failed to cache metrics", str(log_calls[3]))
        self.assertIn("Failed to get cached metrics", str(log_calls[4]))

    def test_integration_session_lifecycle(self):
        """Test complete session data lifecycle (integration test with real cache)."""
        session_id = str(uuid.uuid4())
        session_data = {"user_id": 1, "ide_name": "VSCode", "session_start": "2024-01-01T12:00:00Z"}

        # Set session data
        result_set = self.client.set_session_data(session_id, session_data)
        self.assertTrue(result_set)

        # Get session data
        retrieved_data = self.client.get_session_data(session_id)
        self.assertEqual(retrieved_data, session_data)

        # Delete session data
        result_delete = self.client.delete_session_data(session_id)
        self.assertTrue(result_delete)

        # Verify data is gone
        deleted_data = self.client.get_session_data(session_id)
        self.assertIsNone(deleted_data)

    def test_integration_metrics_lifecycle(self):
        """Test complete metrics lifecycle (integration test with real cache)."""
        user_id = 1
        metrics_data = {
            "total_lines": 1500,
            "files_modified": 8,
            "complexity_score": 22.3,
            "calculated_at": "2024-01-01T12:00:00Z",
        }

        # Set metrics
        result_set = self.client.set_metrics_cache(user_id, metrics_data)
        self.assertTrue(result_set)

        # Get metrics
        retrieved_metrics = self.client.get_metrics_cache(user_id)
        self.assertEqual(retrieved_metrics, metrics_data)

        # Let cache expire or clear it
        cache.clear()

        # Verify metrics are gone
        expired_metrics = self.client.get_metrics_cache(user_id)
        self.assertIsNone(expired_metrics)
