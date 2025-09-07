"""
Tests for custom permissions.
"""

from unittest.mock import MagicMock, Mock

from django.test import RequestFactory, TestCase
from rest_framework.views import APIView

from apps.monitoring.authentication import MonitoringUser
from apps.monitoring.models import DeveloperSession
from apps.monitoring.permissions import CanAccessUserData, IsAuthenticated, IsMonitoringService, IsOwnerOrAdmin


class IsAuthenticatedTest(TestCase):
    """Tests for IsAuthenticated permission."""

    def setUp(self):
        self.factory = RequestFactory()
        self.permission = IsAuthenticated()
        self.view = APIView()

    def test_authenticated_user_has_permission(self):
        """Test that authenticated users have permission."""
        request = self.factory.get("/")
        request.user = MonitoringUser({"user_id": "12345678-1234-5678-9012-123456789abc", "email": "test@example.com"})
        request.user.is_authenticated = True

        self.assertTrue(self.permission.has_permission(request, self.view))

    def test_unauthenticated_user_no_permission(self):
        """Test that unauthenticated users don't have permission."""
        request = self.factory.get("/")
        request.user = None

        self.assertFalse(self.permission.has_permission(request, self.view))

    def test_anonymous_user_no_permission(self):
        """Test that anonymous users don't have permission."""
        request = self.factory.get("/")
        request.user = Mock()
        request.user.is_authenticated = False

        self.assertFalse(self.permission.has_permission(request, self.view))


class IsOwnerOrAdminTest(TestCase):
    """Tests for IsOwnerOrAdmin permission."""

    def setUp(self):
        self.factory = RequestFactory()
        self.permission = IsOwnerOrAdmin()
        self.view = APIView()
        self.session = DeveloperSession.objects.create(user_id="12345678-1234-5678-9012-123456789abc", ide_name="VSCode")

    def test_unauthenticated_user_no_permission(self):
        """Test that unauthenticated users don't have permission."""
        request = self.factory.get("/")
        request.user = None

        self.assertFalse(self.permission.has_permission(request, self.view))

    def test_authenticated_user_has_permission(self):
        """Test that authenticated users have basic permission."""
        request = self.factory.get("/")
        request.user = MonitoringUser({"user_id": "12345678-1234-5678-9012-123456789abc", "email": "test@example.com"})
        request.user.is_authenticated = True

        self.assertTrue(self.permission.has_permission(request, self.view))

    def test_staff_user_has_object_permission(self):
        """Test that staff users have object permission."""
        request = self.factory.get("/")
        request.user = MonitoringUser({"user_id": "87654321-4321-8765-2109-cba987654321", "email": "admin@example.com"})
        request.user.is_authenticated = True
        request.user.is_staff = True

        self.assertTrue(self.permission.has_object_permission(request, self.view, self.session))

    def test_owner_has_object_permission(self):
        """Test that object owner has permission."""
        request = self.factory.get("/")
        request.user = MonitoringUser({"user_id": "12345678-1234-5678-9012-123456789abc", "email": "test@example.com"})
        request.user.is_authenticated = True

        self.assertTrue(self.permission.has_object_permission(request, self.view, self.session))

    def test_non_owner_no_object_permission(self):
        """Test that non-owners don't have object permission."""
        request = self.factory.get("/")
        request.user = MonitoringUser({"user_id": "87654321-4321-8765-2109-cba987654321", "email": "other@example.com"})
        request.user.is_authenticated = True

        self.assertFalse(self.permission.has_object_permission(request, self.view, self.session))

    def test_session_related_object_permission(self):
        """Test permission for objects related to sessions."""
        request = self.factory.get("/")
        request.user = MonitoringUser({"user_id": "12345678-1234-5678-9012-123456789abc", "email": "test@example.com"})
        request.user.is_authenticated = True

        # Mock object with session relation
        obj = Mock()
        obj.session = self.session

        self.assertTrue(self.permission.has_object_permission(request, self.view, obj))

    def test_object_without_user_id_no_permission(self):
        """Test that objects without user_id don't grant permission."""
        request = self.factory.get("/")
        request.user = MonitoringUser({"user_id": "12345678-1234-5678-9012-123456789abc", "email": "test@example.com"})
        request.user.is_authenticated = True

        obj = Mock(spec=[])  # Object without user_id or session

        self.assertFalse(self.permission.has_object_permission(request, self.view, obj))


class CanAccessUserDataTest(TestCase):
    """Tests for CanAccessUserData permission."""

    def setUp(self):
        self.factory = RequestFactory()
        self.permission = CanAccessUserData()
        self.view = APIView()

    def test_unauthenticated_user_no_permission(self):
        """Test that unauthenticated users don't have permission."""
        request = self.factory.get("/")
        request.user = None
        self.view.kwargs = {"user_id": "12345678-1234-5678-9012-123456789abc"}

        self.assertFalse(self.permission.has_permission(request, self.view))

    def test_no_user_id_in_kwargs_allows_access(self):
        """Test that requests without user_id in kwargs are allowed."""
        request = self.factory.get("/")
        request.user = MonitoringUser({"user_id": "12345678-1234-5678-9012-123456789abc", "email": "test@example.com"})
        request.user.is_authenticated = True
        self.view.kwargs = {}

        self.assertTrue(self.permission.has_permission(request, self.view))

    def test_staff_user_can_access_any_data(self):
        """Test that staff users can access any user data."""
        request = self.factory.get("/")
        request.user = MonitoringUser({"user_id": "87654321-4321-8765-2109-cba987654321", "email": "admin@example.com"})
        request.user.is_authenticated = True
        request.user.is_staff = True
        self.view.kwargs = {"user_id": "12345678-1234-5678-9012-123456789abc"}

        self.assertTrue(self.permission.has_permission(request, self.view))

    def test_user_can_access_own_data(self):
        """Test that users can access their own data."""
        request = self.factory.get("/")
        request.user = MonitoringUser({"user_id": "12345678-1234-5678-9012-123456789abc", "email": "test@example.com"})
        request.user.is_authenticated = True
        self.view.kwargs = {"user_id": "12345678-1234-5678-9012-123456789abc"}

        self.assertTrue(self.permission.has_permission(request, self.view))

    def test_user_cannot_access_other_user_data(self):
        """Test that users cannot access other users' data."""
        request = self.factory.get("/")
        request.user = MonitoringUser({"user_id": "12345678-1234-5678-9012-123456789abc", "email": "test@example.com"})
        request.user.is_authenticated = True
        self.view.kwargs = {"user_id": "87654321-4321-8765-2109-cba987654321"}

        self.assertFalse(self.permission.has_permission(request, self.view))


class IsMonitoringServiceTest(TestCase):
    """Tests for IsMonitoringService permission."""

    def setUp(self):
        self.factory = RequestFactory()
        self.permission = IsMonitoringService()
        self.view = APIView()

    def test_service_token_grants_permission(self):
        """Test that service tokens grant permission."""
        request = self.factory.get("/", HTTP_X_SERVICE_TOKEN="service-token-123")
        request.user = None

        self.assertTrue(self.permission.has_permission(request, self.view))

    def test_authenticated_user_has_permission(self):
        """Test that authenticated users have permission."""
        request = self.factory.get("/")
        request.user = MonitoringUser({"user_id": "12345678-1234-5678-9012-123456789abc", "email": "test@example.com"})
        request.user.is_authenticated = True

        self.assertTrue(self.permission.has_permission(request, self.view))

    def test_unauthenticated_user_without_service_token_no_permission(self):
        """Test that unauthenticated users without service token don't have permission."""
        request = self.factory.get("/")
        request.user = None

        self.assertFalse(self.permission.has_permission(request, self.view))

    def test_anonymous_user_without_service_token_no_permission(self):
        """Test that anonymous users without service token don't have permission."""
        request = self.factory.get("/")
        request.user = Mock()
        request.user.is_authenticated = False

        self.assertFalse(self.permission.has_permission(request, self.view))
