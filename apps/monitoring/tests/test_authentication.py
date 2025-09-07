"""
Tests for authentication module.
"""

from unittest.mock import MagicMock, patch

from django.test import RequestFactory, TestCase
from rest_framework.exceptions import AuthenticationFailed

from apps.monitoring.authentication import JWTAuthentication, MonitoringUser


class MonitoringUserTest(TestCase):
    """Tests for MonitoringUser class."""

    def setUp(self):
        self.user_data = {
            "user_id": "12345678-1234-5678-9012-123456789abc",
            "email": "test@example.com",
            "username": "testuser",
            "is_staff": True,
            "is_superuser": False,
        }

    def test_monitoring_user_initialization(self):
        """Test MonitoringUser initialization."""
        user = MonitoringUser(self.user_data)

        self.assertEqual(user.id, "12345678-1234-5678-9012-123456789abc")
        self.assertEqual(user.pk, "12345678-1234-5678-9012-123456789abc")
        self.assertEqual(user.user_id, "12345678-1234-5678-9012-123456789abc")
        self.assertEqual(user.email, "test@example.com")
        self.assertEqual(user.username, "testuser")
        self.assertTrue(user.is_authenticated)
        self.assertFalse(user.is_anonymous)
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_monitoring_user_default_values(self):
        """Test MonitoringUser with minimal data."""
        minimal_data = {"user_id": "12345678-1234-5678-9012-123456789abc"}
        user = MonitoringUser(minimal_data)

        self.assertEqual(user.user_id, "12345678-1234-5678-9012-123456789abc")
        self.assertEqual(user.email, "")
        self.assertEqual(user.username, "")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_monitoring_user_str_representation(self):
        """Test string representation of MonitoringUser."""
        user = MonitoringUser(self.user_data)
        expected_str = "MonitoringUser(12345678-1234-5678-9012-123456789abc)"
        self.assertEqual(str(user), expected_str)

    def test_has_perm_staff_user(self):
        """Test has_perm for staff users."""
        user = MonitoringUser(self.user_data)  # is_staff=True
        self.assertTrue(user.has_perm("any.permission"))

    def test_has_perm_superuser(self):
        """Test has_perm for superusers."""
        superuser_data = self.user_data.copy()
        superuser_data["is_superuser"] = True
        superuser_data["is_staff"] = False
        user = MonitoringUser(superuser_data)

        self.assertTrue(user.has_perm("any.permission"))

    def test_has_perm_regular_user(self):
        """Test has_perm for regular users."""
        regular_user_data = self.user_data.copy()
        regular_user_data["is_staff"] = False
        regular_user_data["is_superuser"] = False
        user = MonitoringUser(regular_user_data)

        self.assertFalse(user.has_perm("any.permission"))

    def test_has_perms_multiple_permissions(self):
        """Test has_perms for multiple permissions."""
        user = MonitoringUser(self.user_data)  # is_staff=True
        self.assertTrue(user.has_perms(["perm1", "perm2", "perm3"]))

        regular_user_data = self.user_data.copy()
        regular_user_data["is_staff"] = False
        regular_user = MonitoringUser(regular_user_data)
        self.assertFalse(regular_user.has_perms(["perm1", "perm2"]))

    def test_has_module_perms_staff_user(self):
        """Test has_module_perms for staff users."""
        user = MonitoringUser(self.user_data)  # is_staff=True
        self.assertTrue(user.has_module_perms("any.module"))

    def test_has_module_perms_regular_user(self):
        """Test has_module_perms for regular users."""
        regular_user_data = self.user_data.copy()
        regular_user_data["is_staff"] = False
        user = MonitoringUser(regular_user_data)

        self.assertFalse(user.has_module_perms("any.module"))

    def test_get_user_data(self):
        """Test get_user_data returns original data."""
        user = MonitoringUser(self.user_data)
        self.assertEqual(user.get_user_data(), self.user_data)


class JWTAuthenticationTest(TestCase):
    """Tests for JWTAuthentication class."""

    def setUp(self):
        self.factory = RequestFactory()
        self.auth = JWTAuthentication()

    def test_authenticate_no_auth_header(self):
        """Test authentication with no Authorization header."""
        request = self.factory.get("/")
        result = self.auth.authenticate(request)

        self.assertIsNone(result)

    def test_authenticate_invalid_auth_header(self):
        """Test authentication with invalid Authorization header format."""
        request = self.factory.get("/", HTTP_AUTHORIZATION="InvalidFormat token123")
        result = self.auth.authenticate(request)

        self.assertIsNone(result)

    @patch("apps.monitoring.authentication.ServiceAuthManager")
    def test_authenticate_success(self, mock_auth_manager):
        """Test successful authentication."""
        # Mock the auth manager
        mock_manager_instance = MagicMock()
        mock_manager_instance.verify_user_token.return_value = {
            "user_id": "12345678-1234-5678-9012-123456789abc",
            "email": "test@example.com",
            "username": "testuser",
        }
        mock_auth_manager.return_value = mock_manager_instance

        request = self.factory.get("/", HTTP_AUTHORIZATION="Bearer valid-jwt-token")
        result = self.auth.authenticate(request)

        self.assertIsNotNone(result)
        user, token = result
        self.assertIsInstance(user, MonitoringUser)
        self.assertEqual(user.user_id, "12345678-1234-5678-9012-123456789abc")
        self.assertEqual(token, "valid-jwt-token")

    @patch("apps.monitoring.authentication.ServiceAuthManager")
    def test_authenticate_invalid_token(self, mock_auth_manager):
        """Test authentication with invalid token."""
        # Mock the auth manager to return None
        mock_manager_instance = MagicMock()
        mock_manager_instance.verify_user_token.return_value = None
        mock_auth_manager.return_value = mock_manager_instance

        request = self.factory.get("/", HTTP_AUTHORIZATION="Bearer invalid-token")

        with self.assertRaises(AuthenticationFailed) as context:
            self.auth.authenticate(request)

        self.assertEqual(str(context.exception), "Invalid token")

    @patch("apps.monitoring.authentication.ServiceAuthManager")
    def test_authenticate_service_error(self, mock_auth_manager):
        """Test authentication with service error."""
        # Mock the auth manager to raise an exception
        mock_manager_instance = MagicMock()
        mock_manager_instance.verify_user_token.side_effect = Exception("Service unavailable")
        mock_auth_manager.return_value = mock_manager_instance

        request = self.factory.get("/", HTTP_AUTHORIZATION="Bearer token123")

        with self.assertRaises(AuthenticationFailed) as context:
            self.auth.authenticate(request)

        self.assertEqual(str(context.exception), "Token verification failed")

    def test_authenticate_header(self):
        """Test authenticate_header method."""
        request = self.factory.get("/")
        header = self.auth.authenticate_header(request)

        self.assertEqual(header, "Bearer")
