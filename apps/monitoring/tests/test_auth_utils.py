"""
Tests for auth_utils module.
"""

from unittest.mock import MagicMock, Mock, patch

import jwt
from django.core.cache import cache
from django.test import TestCase, override_settings
from requests.exceptions import RequestException, Timeout

from apps.monitoring.auth_utils import ServiceAuthManager, get_user_from_request


class ServiceAuthManagerTest(TestCase):
    """Tests for ServiceAuthManager class."""

    def setUp(self):
        """Set up test fixtures."""
        self.auth_manager = ServiceAuthManager()

    @override_settings(JWT_SECRET_KEY="test-secret", AUTH_SERVICE_URL="http://test-auth.com")
    def test_init(self):
        """Test ServiceAuthManager initialization."""
        manager = ServiceAuthManager()
        self.assertEqual(manager.auth_service_url, "http://test-auth.com")
        self.assertEqual(manager.jwt_secret, "test-secret")

    @override_settings(JWT_SECRET_KEY="test-secret")
    @patch("jwt.decode")
    def test_verify_user_token_local_success(self, mock_jwt_decode):
        """Test successful local JWT token verification."""
        mock_jwt_decode.return_value = {"user_id": 1, "email": "test@example.com"}

        result = self.auth_manager.verify_user_token("valid-token")

        self.assertEqual(result, {"user_id": 1, "email": "test@example.com"})
        mock_jwt_decode.assert_called_once_with("valid-token", "test-secret", algorithms=["HS256"])

    @override_settings(JWT_SECRET_KEY="test-secret")
    @patch("jwt.decode")
    @patch.object(ServiceAuthManager, "_verify_with_auth_service")
    def test_verify_user_token_fallback_to_service(self, mock_verify_service, mock_jwt_decode):
        """Test fallback to auth service when local verification fails."""
        mock_jwt_decode.side_effect = jwt.InvalidTokenError("Invalid token")
        mock_verify_service.return_value = {"user_id": 2, "email": "user@example.com"}

        result = self.auth_manager.verify_user_token("invalid-token")

        self.assertEqual(result, {"user_id": 2, "email": "user@example.com"})
        mock_verify_service.assert_called_once_with("invalid-token")

    @override_settings(AUTH_SERVICE_URL="http://test-auth.com")
    @patch("requests.post")
    def test_verify_with_auth_service_success(self, mock_post):
        """Test successful auth service verification."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"user_id": 1, "email": "test@example.com"}
        mock_post.return_value = mock_response

        result = self.auth_manager._verify_with_auth_service("token123")

        self.assertEqual(result, {"user_id": 1, "email": "test@example.com"})
        mock_post.assert_called_once_with("http://test-auth.com/auth/verify-token/", json={"token": "token123"}, timeout=10)

    @override_settings(AUTH_SERVICE_URL="http://test-auth.com")
    @patch("requests.post")
    def test_verify_with_auth_service_failure(self, mock_post):
        """Test auth service verification failure."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response

        result = self.auth_manager._verify_with_auth_service("invalid-token")

        self.assertIsNone(result)

    @override_settings(AUTH_SERVICE_URL="http://test-auth.com")
    @patch("requests.post")
    def test_verify_with_auth_service_request_exception(self, mock_post):
        """Test auth service request exception handling."""
        mock_post.side_effect = RequestException("Connection failed")

        result = self.auth_manager._verify_with_auth_service("token123")

        self.assertIsNone(result)

    @override_settings(AUTH_SERVICE_URL="http://test-auth.com")
    @patch("requests.post")
    def test_verify_with_auth_service_timeout(self, mock_post):
        """Test auth service timeout handling."""
        mock_post.side_effect = Timeout("Request timed out")

        result = self.auth_manager._verify_with_auth_service("token123")

        self.assertIsNone(result)

    def tearDown(self):
        """Clear cache after each test."""
        cache.clear()

    @override_settings(AUTH_SERVICE_URL="http://test-auth.com")
    @patch("requests.get")
    def test_get_user_info_from_cache(self, mock_get):
        """Test getting user info from cache."""
        # Set up cache
        user_info = {"user_id": 1, "email": "test@example.com", "username": "testuser"}
        cache.set("user_info:1", user_info, 300)

        result = self.auth_manager.get_user_info(1)

        self.assertEqual(result, user_info)
        mock_get.assert_not_called()  # Should not make HTTP request

    @override_settings(AUTH_SERVICE_URL="http://test-auth.com")
    @patch("requests.get")
    def test_get_user_info_from_service_success(self, mock_get):
        """Test successful user info retrieval from auth service."""
        user_info = {"user_id": 1, "email": "test@example.com", "username": "testuser"}
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = user_info
        mock_get.return_value = mock_response

        result = self.auth_manager.get_user_info(1)

        self.assertEqual(result, user_info)
        mock_get.assert_called_once_with("http://test-auth.com/auth/users/1/", timeout=10)

        # Verify it was cached
        cached_result = cache.get("user_info:1")
        self.assertEqual(cached_result, user_info)

    @override_settings(AUTH_SERVICE_URL="http://test-auth.com")
    @patch("requests.get")
    def test_get_user_info_service_failure(self, mock_get):
        """Test user info retrieval failure from auth service."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = self.auth_manager.get_user_info(1)

        self.assertIsNone(result)

    @override_settings(AUTH_SERVICE_URL="http://test-auth.com")
    @patch("requests.get")
    def test_get_user_info_request_exception(self, mock_get):
        """Test user info retrieval request exception."""
        mock_get.side_effect = RequestException("Connection failed")

        result = self.auth_manager.get_user_info(1)

        self.assertIsNone(result)

    @override_settings(AUTH_SERVICE_URL="http://test-auth.com")
    @patch("requests.get")
    def test_get_user_info_timeout(self, mock_get):
        """Test user info retrieval timeout."""
        mock_get.side_effect = Timeout("Request timed out")

        result = self.auth_manager.get_user_info(1)

        self.assertIsNone(result)


class GetUserFromRequestTest(TestCase):
    """Tests for get_user_from_request function."""

    def test_no_auth_header(self):
        """Test request without Authorization header."""
        request = Mock()
        request.META = {}

        result = get_user_from_request(request)

        self.assertIsNone(result)

    def test_invalid_auth_header_format(self):
        """Test request with invalid Authorization header format."""
        request = Mock()
        request.META = {"HTTP_AUTHORIZATION": "InvalidFormat token123"}

        result = get_user_from_request(request)

        self.assertIsNone(result)

    def test_missing_bearer_prefix(self):
        """Test request without Bearer prefix."""
        request = Mock()
        request.META = {"HTTP_AUTHORIZATION": "token123"}

        result = get_user_from_request(request)

        self.assertIsNone(result)

    @patch("apps.monitoring.auth_utils.ServiceAuthManager")
    def test_valid_token_success(self, mock_auth_manager_class):
        """Test successful token verification."""
        mock_auth_manager = Mock()
        mock_auth_manager.verify_user_token.return_value = {"user_id": 1, "email": "test@example.com"}
        mock_auth_manager_class.return_value = mock_auth_manager

        request = Mock()
        request.META = {"HTTP_AUTHORIZATION": "Bearer valid-token"}

        result = get_user_from_request(request)

        self.assertEqual(result, 1)
        mock_auth_manager.verify_user_token.assert_called_once_with("valid-token")

    @patch("apps.monitoring.auth_utils.ServiceAuthManager")
    def test_invalid_token(self, mock_auth_manager_class):
        """Test invalid token verification."""
        mock_auth_manager = Mock()
        mock_auth_manager.verify_user_token.return_value = None
        mock_auth_manager_class.return_value = mock_auth_manager

        request = Mock()
        request.META = {"HTTP_AUTHORIZATION": "Bearer invalid-token"}

        result = get_user_from_request(request)

        self.assertIsNone(result)

    @patch("apps.monitoring.auth_utils.ServiceAuthManager")
    def test_token_without_user_id(self, mock_auth_manager_class):
        """Test token verification without user_id in response."""
        mock_auth_manager = Mock()
        mock_auth_manager.verify_user_token.return_value = {"email": "test@example.com"}
        mock_auth_manager_class.return_value = mock_auth_manager

        request = Mock()
        request.META = {"HTTP_AUTHORIZATION": "Bearer token-without-user-id"}

        result = get_user_from_request(request)

        self.assertIsNone(result)

    @patch("apps.monitoring.auth_utils.ServiceAuthManager")
    def test_auth_manager_exception(self, mock_auth_manager_class):
        """Test auth manager initialization exception."""
        mock_auth_manager_class.side_effect = Exception("Config error")

        request = Mock()
        request.META = {"HTTP_AUTHORIZATION": "Bearer valid-token"}

        # Should not raise exception, should return None
        result = get_user_from_request(request)

        self.assertIsNone(result)
