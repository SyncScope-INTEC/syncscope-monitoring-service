"""
Tests for authentication backends.
"""

import json
from unittest.mock import MagicMock, Mock, patch

import requests
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings

from apps.monitoring.auth_backends import AuthServiceBackend, CachedAuthServiceBackend


class AuthServiceBackendTest(TestCase):
    """Tests for AuthServiceBackend authentication backend."""

    def setUp(self):
        self.backend = AuthServiceBackend()
        cache.clear()  # Clear cache before each test

    def test_authenticate_with_none_username(self):
        """Test authentication with None username."""
        result = self.backend.authenticate(None, username=None, password="password")
        self.assertIsNone(result)

    def test_authenticate_with_none_password(self):
        """Test authentication with None password."""
        result = self.backend.authenticate(None, username="user@example.com", password=None)
        self.assertIsNone(result)

    @patch("apps.monitoring.auth_backends.requests.post")
    def test_authenticate_with_auth_service_failure(self, mock_post):
        """Test authentication when auth service returns failure."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_post.return_value = mock_response

        result = self.backend.authenticate(None, username="user@example.com", password="wrongpass")
        self.assertIsNone(result)

    @patch("apps.monitoring.auth_backends.requests.post")
    @patch("apps.monitoring.auth_backends.requests.get")
    def test_authenticate_success_with_staff_user(self, mock_get, mock_post):
        """Test successful authentication with staff user."""
        # Mock login response
        mock_login_response = MagicMock()
        mock_login_response.status_code = 200
        mock_login_response.json.return_value = {"access_token": "test-token"}
        mock_post.return_value = mock_login_response

        # Mock profile responses
        mock_profile_response = MagicMock()
        mock_profile_response.status_code = 200
        mock_profile_response.json.return_value = {
            "email": "admin@example.com",
            "first_name": "Admin",
            "last_name": "User",
            "is_staff": True,
            "is_superuser": False,
            "is_active": True,
        }
        mock_get.return_value = mock_profile_response

        result = self.backend.authenticate(None, username="admin@example.com", password="password")

        self.assertIsNotNone(result)
        self.assertIsInstance(result, User)
        self.assertEqual(result.email, "admin@example.com")
        self.assertTrue(result.is_staff)

    @patch("apps.monitoring.auth_backends.requests.post")
    @patch("apps.monitoring.auth_backends.requests.get")
    def test_authenticate_success_with_superuser(self, mock_get, mock_post):
        """Test successful authentication with superuser."""
        # Mock login response
        mock_login_response = MagicMock()
        mock_login_response.status_code = 200
        mock_login_response.json.return_value = {"access_token": "test-token"}
        mock_post.return_value = mock_login_response

        # Mock profile responses - first call for staff check, second for user creation
        mock_profile_response = MagicMock()
        mock_profile_response.status_code = 200
        mock_profile_response.json.return_value = {
            "email": "super@example.com",
            "first_name": "Super",
            "last_name": "User",
            "is_staff": False,
            "is_superuser": True,
            "is_active": True,
        }
        mock_get.return_value = mock_profile_response

        result = self.backend.authenticate(None, username="super@example.com", password="password")

        self.assertIsNotNone(result)
        self.assertTrue(result.is_superuser)

    @patch("apps.monitoring.auth_backends.requests.post")
    @patch("apps.monitoring.auth_backends.requests.get")
    def test_authenticate_non_staff_user_rejected(self, mock_get, mock_post):
        """Test that non-staff users are rejected."""
        # Mock login response
        mock_login_response = MagicMock()
        mock_login_response.status_code = 200
        mock_login_response.json.return_value = {"access_token": "test-token"}
        mock_post.return_value = mock_login_response

        # Mock profile response for non-staff user
        mock_profile_response = MagicMock()
        mock_profile_response.status_code = 200
        mock_profile_response.json.return_value = {"is_staff": False, "is_superuser": False}
        mock_get.return_value = mock_profile_response

        result = self.backend.authenticate(None, username="user@example.com", password="password")
        self.assertIsNone(result)

    @patch("apps.monitoring.auth_backends.requests.post")
    def test_authenticate_requests_exception(self, mock_post):
        """Test authentication when requests raises exception."""
        mock_post.side_effect = requests.RequestException("Connection error")

        result = self.backend.authenticate(None, username="user@example.com", password="password")
        self.assertIsNone(result)

    def test_get_user_existing(self):
        """Test get_user with existing user."""
        user = User.objects.create(username="test@example.com")
        result = self.backend.get_user(user.id)
        self.assertEqual(result, user)

    def test_get_user_nonexistent(self):
        """Test get_user with non-existent user."""
        result = self.backend.get_user(99999)
        self.assertIsNone(result)

    @override_settings(AUTH_SERVICE_URL="http://custom-auth.com")
    @patch("apps.monitoring.auth_backends.requests.post")
    def test_authenticate_with_custom_auth_service_url(self, mock_post):
        """Test authentication uses custom AUTH_SERVICE_URL setting."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response

        self.backend.authenticate(None, username="user@example.com", password="password")

        # Verify the correct URL was called
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "http://custom-auth.com/auth/login")

    @patch("apps.monitoring.auth_backends.requests.get")
    def test_is_staff_user_no_token(self, mock_get):
        """Test _is_staff_user with no token."""
        result = self.backend._is_staff_user(None)
        self.assertFalse(result)
        mock_get.assert_not_called()

    @patch("apps.monitoring.auth_backends.requests.get")
    def test_is_staff_user_request_exception(self, mock_get):
        """Test _is_staff_user when request raises exception."""
        mock_get.side_effect = requests.RequestException("Network error")

        result = self.backend._is_staff_user("test-token")
        self.assertFalse(result)

    @patch("apps.monitoring.auth_backends.requests.get")
    def test_is_staff_user_non_200_response(self, mock_get):
        """Test _is_staff_user with non-200 response."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        result = self.backend._is_staff_user("test-token")
        self.assertFalse(result)

    @patch("apps.monitoring.auth_backends.requests.get")
    def test_get_user_profile_no_token(self, mock_get):
        """Test _get_user_profile with no token."""
        result = self.backend._get_user_profile(None)
        self.assertIsNone(result)
        mock_get.assert_not_called()

    @patch("apps.monitoring.auth_backends.requests.get")
    def test_get_user_profile_request_exception(self, mock_get):
        """Test _get_user_profile when request raises exception."""
        mock_get.side_effect = requests.RequestException("Network error")

        result = self.backend._get_user_profile("test-token")
        self.assertIsNone(result)

    @patch("apps.monitoring.auth_backends.requests.get")
    def test_get_user_profile_non_200_response(self, mock_get):
        """Test _get_user_profile with non-200 response."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = self.backend._get_user_profile("test-token")
        self.assertIsNone(result)

    @patch("apps.monitoring.auth_backends.requests.get")
    def test_get_or_create_local_user_no_profile(self, mock_get):
        """Test _get_or_create_local_user when profile fetch fails."""
        mock_get.return_value = Mock(status_code=404)

        result = self.backend._get_or_create_local_user({"access_token": "test-token"})
        self.assertIsNone(result)

    @patch("apps.monitoring.auth_backends.requests.get")
    def test_get_or_create_local_user_no_email(self, mock_get):
        """Test _get_or_create_local_user when profile has no email."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"first_name": "Test"}  # No email
        mock_get.return_value = mock_response

        result = self.backend._get_or_create_local_user({"access_token": "test-token"})
        self.assertIsNone(result)

    @patch("apps.monitoring.auth_backends.requests.get")
    def test_get_or_create_local_user_update_existing(self, mock_get):
        """Test _get_or_create_local_user updates existing user."""
        # Create existing user
        existing_user = User.objects.create(
            username="test@example.com", email="test@example.com", first_name="Old", last_name="Name"
        )

        # Mock profile response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "email": "test@example.com",
            "first_name": "New",
            "last_name": "Name",
            "is_staff": True,
            "is_superuser": False,
            "is_active": True,
        }
        mock_get.return_value = mock_response

        result = self.backend._get_or_create_local_user({"access_token": "test-token"})

        self.assertEqual(result.id, existing_user.id)  # Same user
        self.assertEqual(result.first_name, "New")  # Updated name
        self.assertTrue(result.is_staff)


class CachedAuthServiceBackendTest(TestCase):
    """Tests for CachedAuthServiceBackend."""

    def setUp(self):
        self.backend = CachedAuthServiceBackend()
        cache.clear()

    def test_authenticate_with_none_credentials(self):
        """Test cached backend with None credentials."""
        result = self.backend.authenticate(None, username=None, password="password")
        self.assertIsNone(result)

    @patch("apps.monitoring.auth_backends.AuthServiceBackend.authenticate")
    def test_authenticate_cached_failure(self, mock_parent_auth):
        """Test that failed attempts are cached."""
        mock_parent_auth.return_value = None

        # First attempt
        result1 = self.backend.authenticate(None, username="user@example.com", password="wrong")
        self.assertIsNone(result1)

        # Second attempt should use cache
        result2 = self.backend.authenticate(None, username="user@example.com", password="wrong")
        self.assertIsNone(result2)

        # Parent authenticate should only be called once due to caching
        self.assertEqual(mock_parent_auth.call_count, 1)

    @patch("apps.monitoring.auth_backends.AuthServiceBackend.authenticate")
    def test_authenticate_success_no_cache(self, mock_parent_auth):
        """Test that successful attempts are not cached as failures."""
        mock_user = User(username="user@example.com")
        mock_parent_auth.return_value = mock_user

        result = self.backend.authenticate(None, username="user@example.com", password="correct")
        self.assertEqual(result, mock_user)

        # No cache entry should be created for successful auth
        cache_key = "auth_fail_user@example.com"
        self.assertIsNone(cache.get(cache_key))
