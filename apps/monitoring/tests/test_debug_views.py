"""
Tests for debug_views module.
"""

import json
from unittest.mock import Mock, patch

import requests
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse


class TestAuthServiceViewTest(TestCase):
    """Tests for test_auth_service debug view."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.url = "/debug/test-auth-service/"  # URL pattern from urls.py

    def test_test_auth_service_missing_credentials(self):
        """Test debug endpoint with missing credentials."""
        # Missing both username and password
        response = self.client.post(self.url, data=json.dumps({}), content_type="application/json")

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["error"], "Username and password required")
        self.assertEqual(data["status"], "failed")

    def test_test_auth_service_missing_username(self):
        """Test debug endpoint with missing username."""
        response = self.client.post(self.url, data=json.dumps({"password": "testpass"}), content_type="application/json")

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["error"], "Username and password required")
        self.assertEqual(data["status"], "failed")

    def test_test_auth_service_missing_password(self):
        """Test debug endpoint with missing password."""
        response = self.client.post(self.url, data=json.dumps({"username": "testuser"}), content_type="application/json")

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["error"], "Username and password required")
        self.assertEqual(data["status"], "failed")

    @override_settings(AUTH_SERVICE_URL="http://test-auth-service.com")
    @patch("apps.monitoring.debug_views.requests.post")
    def test_test_auth_service_successful_login(self, mock_post):
        """Test successful authentication through debug endpoint."""
        # Mock successful login response
        login_response = Mock()
        login_response.status_code = 200
        login_response.json.return_value = {"access_token": "test-token"}
        login_response.text = '{"access_token": "test-token"}'

        # Mock successful profile response
        profile_response = Mock()
        profile_response.status_code = 200
        profile_response.json.return_value = {
            "email": "test@example.com",
            "is_staff": True,
            "is_superuser": False,
            "is_active": True,
        }
        profile_response.text = '{"email": "test@example.com", "is_staff": true}'

        # Configure requests.post to return different responses based on call
        mock_post.side_effect = [login_response, profile_response]

        response = self.client.post(
            self.url,
            data=json.dumps({"username": "test@example.com", "password": "testpass"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["auth_service_url"], "http://test-auth-service.com")
        self.assertEqual(data["login_url"], "http://test-auth-service.com/auth/login")
        self.assertEqual(data["login_response_status"], 200)
        self.assertIn("profile_response_status", data)
        self.assertEqual(data["profile_response_status"], 200)
        self.assertEqual(data["status"], "success")
        self.assertIn("user_info", data)
        self.assertEqual(data["user_info"]["email"], "test@example.com")
        self.assertTrue(data["user_info"]["is_staff"])

        # Verify the correct API calls were made
        self.assertEqual(mock_post.call_count, 2)

    @override_settings(AUTH_SERVICE_URL="http://test-auth-service.com")
    @patch("apps.monitoring.debug_views.requests.post")
    def test_test_auth_service_login_failed(self, mock_post):
        """Test failed login through debug endpoint."""
        login_response = Mock()
        login_response.status_code = 401
        login_response.text = '{"error": "Invalid credentials"}'

        mock_post.return_value = login_response

        response = self.client.post(
            self.url,
            data=json.dumps({"username": "test@example.com", "password": "wrongpass"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["login_response_status"], 401)
        self.assertEqual(data["status"], "login_failed")
        self.assertIn("login_response_text", data)

    @override_settings(AUTH_SERVICE_URL="http://test-auth-service.com")
    @patch("apps.monitoring.debug_views.requests.post")
    @patch("apps.monitoring.debug_views.requests.get")
    def test_test_auth_service_profile_failed(self, mock_get, mock_post):
        """Test successful login but failed profile fetch."""
        login_response = Mock()
        login_response.status_code = 200
        login_response.json.return_value = {"access_token": "test-token"}
        login_response.text = '{"access_token": "test-token"}'
        mock_post.return_value = login_response

        profile_response = Mock()
        profile_response.status_code = 403
        profile_response.text = '{"error": "Forbidden"}'
        mock_get.return_value = profile_response

        response = self.client.post(
            self.url,
            data=json.dumps({"username": "test@example.com", "password": "testpass"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["login_response_status"], 200)
        self.assertEqual(data["profile_response_status"], 403)
        self.assertEqual(data["status"], "profile_failed")

    @override_settings(AUTH_SERVICE_URL="http://test-auth-service.com")
    @patch("apps.monitoring.debug_views.requests.post")
    def test_test_auth_service_no_token(self, mock_post):
        """Test login response without access token."""
        login_response = Mock()
        login_response.status_code = 200
        login_response.json.return_value = {"message": "Success but no token"}
        login_response.text = '{"message": "Success but no token"}'
        mock_post.return_value = login_response

        response = self.client.post(
            self.url,
            data=json.dumps({"username": "test@example.com", "password": "testpass"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["login_response_status"], 200)
        self.assertEqual(data["status"], "no_token")

    @override_settings(AUTH_SERVICE_URL="http://test-auth-service.com")
    @patch("apps.monitoring.debug_views.requests.post")
    def test_test_auth_service_connection_failed(self, mock_post):
        """Test connection failure to auth service."""
        mock_post.side_effect = requests.ConnectionError("Connection failed")

        response = self.client.post(
            self.url,
            data=json.dumps({"username": "test@example.com", "password": "testpass"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["status"], "connection_failed")
        self.assertIn("error", data)
        self.assertIn("Connection failed", data["error"])

    @override_settings(AUTH_SERVICE_URL="http://test-auth-service.com")
    @patch("apps.monitoring.debug_views.requests.post")
    def test_test_auth_service_timeout(self, mock_post):
        """Test timeout when connecting to auth service."""
        mock_post.side_effect = requests.Timeout("Request timeout")

        response = self.client.post(
            self.url,
            data=json.dumps({"username": "test@example.com", "password": "testpass"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["status"], "connection_failed")
        self.assertIn("error", data)

    @patch("apps.monitoring.debug_views.requests.post")
    @patch("apps.monitoring.debug_views.getattr")
    def test_test_auth_service_default_url(self, mock_getattr, mock_post):
        """Test debug endpoint uses default URL when AUTH_SERVICE_URL not set."""
        # Mock getattr to return the default value when AUTH_SERVICE_URL is not set
        mock_getattr.return_value = "http://localhost:8000"

        login_response = Mock()
        login_response.status_code = 401
        login_response.text = "Unauthorized"
        mock_post.return_value = login_response

        response = self.client.post(
            self.url,
            data=json.dumps({"username": "test@example.com", "password": "testpass"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["auth_service_url"], "http://localhost:8000")
        self.assertEqual(data["login_url"], "http://localhost:8000/auth/login")

    def test_test_auth_service_invalid_json(self):
        """Test debug endpoint with invalid JSON."""
        response = self.client.post(self.url, data="invalid json", content_type="application/json")

        self.assertEqual(response.status_code, 500)
        data = response.json()

        self.assertEqual(data["status"], "error")
        self.assertIn("error", data)

    def test_test_auth_service_get_method_not_allowed(self):
        """Test debug endpoint only allows POST."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)  # Method Not Allowed

    @override_settings(AUTH_SERVICE_URL="http://test-auth-service.com")
    @patch("apps.monitoring.debug_views.requests.post")
    def test_test_auth_service_response_text_truncation(self, mock_post):
        """Test that long response text is truncated."""
        long_text = "x" * 1000  # 1000 character response
        login_response = Mock()
        login_response.status_code = 400
        login_response.text = long_text
        mock_post.return_value = login_response

        response = self.client.post(
            self.url,
            data=json.dumps({"username": "test@example.com", "password": "testpass"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Response text should be truncated to 500 characters
        self.assertEqual(len(data["login_response_text"]), 500)
        self.assertEqual(data["login_response_text"], "x" * 500)


class TestSettingsViewTest(TestCase):
    """Tests for test_settings debug view."""

    def setUp(self):
        """Set up test fixtures."""
        self.url = "/debug/test-settings/"  # URL pattern from urls.py

    @override_settings(AUTH_SERVICE_URL="http://test-auth-service.com", DEBUG=True, ENVIRONMENT="test")
    def test_test_settings_view(self):
        """Test settings debug endpoint returns current settings."""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["AUTH_SERVICE_URL"], "http://test-auth-service.com")
        self.assertTrue(data["DEBUG"])
        self.assertEqual(data["ENVIRONMENT"], "test")
        self.assertIn("AUTHENTICATION_BACKENDS", data)
        self.assertIsInstance(data["AUTHENTICATION_BACKENDS"], list)

    @patch("apps.monitoring.debug_views.getattr")
    def test_test_settings_view_missing_values(self, mock_getattr):
        """Test settings debug endpoint with missing optional settings."""

        def getattr_side_effect(obj, name, default=None):
            if name in ["AUTH_SERVICE_URL", "ENVIRONMENT"]:
                return "Not set"
            # Return actual values for other settings
            return getattr(obj, name, default)

        mock_getattr.side_effect = getattr_side_effect

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["AUTH_SERVICE_URL"], "Not set")
        self.assertEqual(data["ENVIRONMENT"], "Not set")
        self.assertIn("DEBUG", data)  # DEBUG should always be present
        self.assertIn("AUTHENTICATION_BACKENDS", data)

    def test_test_settings_post_method_not_allowed(self):
        """Test that test_settings only allows GET method."""
        response = self.client.post(self.url, data={})
        self.assertEqual(response.status_code, 405)  # Method Not Allowed

    def test_test_settings_put_method_not_allowed(self):
        """Test that test_settings doesn't allow PUT method."""
        response = self.client.put(self.url, data={})
        self.assertEqual(response.status_code, 405)  # Method Not Allowed
