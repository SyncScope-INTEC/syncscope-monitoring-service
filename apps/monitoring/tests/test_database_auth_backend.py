"""
Tests for database_auth_backend module.
"""

import time
from unittest.mock import MagicMock, Mock, patch

import requests
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings

from apps.monitoring.database_auth_backend import AuthServiceAPIBackend, CachedAuthServiceAPIBackend


class AuthServiceAPIBackendTest(TestCase):
    """Tests for AuthServiceAPIBackend class."""

    def setUp(self):
        """Set up test fixtures."""
        self.backend = AuthServiceAPIBackend()
        self.auth_service_url = "http://test-auth-service.com"

        # Clear any existing users
        User.objects.all().delete()
        cache.clear()

    @override_settings(AUTH_SERVICE_URL="http://test-auth-service.com")
    def test_backend_initialization(self):
        """Test backend initialization with settings."""
        backend = AuthServiceAPIBackend()
        self.assertEqual(backend.auth_service_url, "http://test-auth-service.com")

    def test_authenticate_missing_credentials(self):
        """Test authentication with missing credentials."""
        # Missing username
        result = self.backend.authenticate(None, username=None, password="password")
        self.assertIsNone(result)

        # Missing password
        result = self.backend.authenticate(None, username="user@example.com", password=None)
        self.assertIsNone(result)

        # Missing both
        result = self.backend.authenticate(None, username=None, password=None)
        self.assertIsNone(result)

    @patch("apps.monitoring.database_auth_backend.requests.post")
    def test_authenticate_success_admin_user(self, mock_post):
        """Test successful authentication for admin user."""
        # Mock successful auth service response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "user": {
                "email": "admin@example.com",
                "first_name": "Admin",
                "last_name": "User",
                "role": "admin",
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            }
        }
        mock_post.return_value = mock_response

        result = self.backend.authenticate(None, username="admin@example.com", password="password")

        self.assertIsNotNone(result)
        self.assertIsInstance(result, User)
        self.assertEqual(result.email, "admin@example.com")
        self.assertEqual(result.username, "admin@example.com")
        self.assertTrue(result.is_staff)
        self.assertTrue(result.is_superuser)
        self.assertTrue(result.is_active)

    @patch("apps.monitoring.database_auth_backend.requests.post")
    def test_authenticate_success_supervisor_user(self, mock_post):
        """Test successful authentication for supervisor user."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "user": {
                "email": "supervisor@example.com",
                "first_name": "Super",
                "last_name": "Visor",
                "role": "supervisor",
                "is_staff": False,
                "is_superuser": False,
                "is_active": True,
            }
        }
        mock_post.return_value = mock_response

        result = self.backend.authenticate(None, username="supervisor@example.com", password="password")

        self.assertIsNotNone(result)
        self.assertTrue(result.is_staff)  # Should be True due to supervisor role
        self.assertFalse(result.is_superuser)

    @patch("apps.monitoring.database_auth_backend.requests.post")
    def test_authenticate_non_staff_user(self, mock_post):
        """Test authentication for non-staff user (should be rejected)."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "user": {
                "email": "developer@example.com",
                "role": "developer",
                "is_staff": False,
                "is_superuser": False,
                "is_active": True,
            }
        }
        mock_post.return_value = mock_response

        result = self.backend.authenticate(None, username="developer@example.com", password="password")

        # Should return None because user doesn't have admin privileges
        self.assertIsNone(result)

    @patch("apps.monitoring.database_auth_backend.requests.post")
    def test_authenticate_inactive_user(self, mock_post):
        """Test authentication for inactive user."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "user": {
                "email": "inactive@example.com",
                "role": "admin",
                "is_staff": True,
                "is_superuser": True,
                "is_active": False,
            }
        }
        mock_post.return_value = mock_response

        result = self.backend.authenticate(None, username="inactive@example.com", password="password")

        self.assertIsNone(result)

    @patch("apps.monitoring.database_auth_backend.requests.post")
    def test_authenticate_failed_credentials(self, mock_post):
        """Test authentication with failed credentials."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response

        result = self.backend.authenticate(None, username="user@example.com", password="wrongpassword")

        self.assertIsNone(result)

    @patch("apps.monitoring.database_auth_backend.requests.post")
    def test_authenticate_service_error(self, mock_post):
        """Test authentication with service error."""
        mock_post.side_effect = requests.exceptions.RequestException("Service unavailable")

        result = self.backend.authenticate(None, username="user@example.com", password="password")

        self.assertIsNone(result)

    def test_get_user_existing(self):
        """Test get_user with existing user."""
        user = User.objects.create_user(username="test@example.com", email="test@example.com")

        result = self.backend.get_user(user.id)

        self.assertEqual(result, user)

    def test_get_user_nonexistent(self):
        """Test get_user with non-existent user ID."""
        result = self.backend.get_user(999)

        self.assertIsNone(result)

    @patch("apps.monitoring.database_auth_backend.requests.post")
    def test_authenticate_with_service_timeout_retry(self, mock_post):
        """Test authentication with timeout and retry logic."""
        # First two calls timeout, third succeeds
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "user": {"email": "admin@example.com", "role": "admin", "is_staff": True, "is_superuser": True, "is_active": True}
        }

        mock_post.side_effect = [requests.exceptions.Timeout("Timeout"), requests.exceptions.Timeout("Timeout"), mock_response]

        with patch("time.sleep"):  # Speed up test by mocking sleep
            result = self.backend.authenticate(None, username="admin@example.com", password="password")

        self.assertIsNotNone(result)
        self.assertEqual(mock_post.call_count, 3)

    @patch("apps.monitoring.database_auth_backend.requests.post")
    def test_authenticate_with_service_all_attempts_fail(self, mock_post):
        """Test authentication when all retry attempts fail."""
        mock_post.side_effect = requests.exceptions.Timeout("Timeout")

        with patch("time.sleep"):  # Speed up test by mocking sleep
            result = self.backend.authenticate(None, username="admin@example.com", password="password")

        self.assertIsNone(result)
        self.assertEqual(mock_post.call_count, 3)  # Max retries

    @patch("apps.monitoring.database_auth_backend.requests.post")
    def test_authenticate_updates_existing_user(self, mock_post):
        """Test that authentication updates existing local user."""
        # Create existing user
        existing_user = User.objects.create_user(
            username="admin@example.com", email="admin@example.com", first_name="Old Name", is_staff=False
        )

        # Mock auth response with updated info
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "user": {
                "email": "admin@example.com",
                "first_name": "New Name",
                "last_name": "Updated",
                "role": "admin",
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            }
        }
        mock_post.return_value = mock_response

        result = self.backend.authenticate(None, username="admin@example.com", password="password")

        # Refresh from database
        updated_user = User.objects.get(id=existing_user.id)

        self.assertEqual(result, updated_user)
        self.assertEqual(updated_user.first_name, "New Name")
        self.assertEqual(updated_user.last_name, "Updated")
        self.assertTrue(updated_user.is_staff)
        self.assertTrue(updated_user.is_superuser)

    @patch("apps.monitoring.database_auth_backend.requests.post")
    def test_authenticate_with_service_http_error(self, mock_post):
        """Test authentication with HTTP error codes."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response

        result = self.backend.authenticate(None, username="user@example.com", password="password")

        self.assertIsNone(result)

    @patch("apps.monitoring.database_auth_backend.requests.post")
    def test_get_or_create_local_user_exception(self, mock_post):
        """Test _get_or_create_local_user with exception."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "user": {"email": "test@example.com", "role": "admin", "is_staff": True, "is_active": True}
        }
        mock_post.return_value = mock_response

        # Mock User.objects.get_or_create to raise an exception
        with patch.object(User.objects, "get_or_create", side_effect=Exception("DB Error")):
            result = self.backend.authenticate(None, username="test@example.com", password="password")

        self.assertIsNone(result)


class CachedAuthServiceAPIBackendTest(TestCase):
    """Tests for CachedAuthServiceAPIBackend class."""

    def setUp(self):
        """Set up test fixtures."""
        self.backend = CachedAuthServiceAPIBackend()
        cache.clear()
        User.objects.all().delete()

    def test_authenticate_missing_credentials(self):
        """Test cached authentication with missing credentials."""
        result = self.backend.authenticate(None, username=None, password="password")
        self.assertIsNone(result)

        result = self.backend.authenticate(None, username="user@example.com", password=None)
        self.assertIsNone(result)

    @patch("apps.monitoring.database_auth_backend.AuthServiceAPIBackend.authenticate")
    def test_authenticate_success_no_cache(self, mock_super_auth):
        """Test successful authentication when not cached."""
        mock_user = User.objects.create_user(username="admin@example.com", email="admin@example.com", is_staff=True)
        mock_super_auth.return_value = mock_user

        result = self.backend.authenticate(None, username="admin@example.com", password="password")

        self.assertEqual(result, mock_user)
        mock_super_auth.assert_called_once()

    @patch("apps.monitoring.database_auth_backend.AuthServiceAPIBackend.authenticate")
    def test_authenticate_cached_failure(self, mock_super_auth):
        """Test authentication with cached failure."""
        # Set up cached failure
        cache_key = "auth_fail_user@example.com"
        cache.set(cache_key, True, timeout=300)

        result = self.backend.authenticate(None, username="user@example.com", password="password")

        self.assertIsNone(result)
        # Should not call parent authenticate due to cache
        mock_super_auth.assert_not_called()

    @patch("apps.monitoring.database_auth_backend.AuthServiceAPIBackend.authenticate")
    def test_authenticate_failure_gets_cached(self, mock_super_auth):
        """Test that authentication failure gets cached."""
        mock_super_auth.return_value = None

        result = self.backend.authenticate(None, username="user@example.com", password="wrongpassword")

        self.assertIsNone(result)

        # Check that failure is cached
        cache_key = "auth_fail_user@example.com"
        cached_failure = cache.get(cache_key)
        self.assertTrue(cached_failure)

    @patch("apps.monitoring.database_auth_backend.AuthServiceAPIBackend.authenticate")
    def test_authenticate_success_no_caching(self, mock_super_auth):
        """Test that successful authentication doesn't get cached as failure."""
        mock_user = User.objects.create_user(username="admin@example.com", email="admin@example.com", is_staff=True)
        mock_super_auth.return_value = mock_user

        result = self.backend.authenticate(None, username="admin@example.com", password="password")

        self.assertEqual(result, mock_user)

        # Check that success is not cached as failure
        cache_key = "auth_fail_admin@example.com"
        cached_failure = cache.get(cache_key)
        self.assertIsNone(cached_failure)

    @patch("apps.monitoring.database_auth_backend.AuthServiceAPIBackend.authenticate")
    def test_authenticate_cache_key_format(self, mock_super_auth):
        """Test that cache key is formatted correctly."""
        mock_super_auth.return_value = None

        username = "test.user+123@example.com"
        result = self.backend.authenticate(None, username=username, password="password")

        self.assertIsNone(result)

        # Check cache key format
        expected_cache_key = f"auth_fail_{username}"
        cached_failure = cache.get(expected_cache_key)
        self.assertTrue(cached_failure)
