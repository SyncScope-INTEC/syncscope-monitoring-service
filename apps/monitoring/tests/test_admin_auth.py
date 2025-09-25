"""
Tests for admin_auth module.
"""

from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.http import HttpRequest, HttpResponseRedirect
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.monitoring.admin_auth import AuthServiceAdminSite, AuthServiceUserAdmin, monitoring_admin_site

User = get_user_model()


class AuthServiceAdminSiteTest(TestCase):
    """Tests for AuthServiceAdminSite class."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.admin_site = AuthServiceAdminSite(name="test_admin")

        # Create test user
        self.test_user = User.objects.create_user(
            username="test@example.com", email="test@example.com", password="testpass", is_staff=True, is_active=True
        )

    def test_admin_site_properties(self):
        """Test that admin site has correct properties."""
        self.assertEqual(self.admin_site.site_header, "SyncScope Monitoring Service Administration")
        self.assertEqual(self.admin_site.site_title, "SyncScope Monitoring Admin")
        self.assertEqual(self.admin_site.index_title, "Monitoring Service Dashboard")

    def test_monitoring_admin_site_instance(self):
        """Test that monitoring_admin_site is properly configured."""
        self.assertIsInstance(monitoring_admin_site, AuthServiceAdminSite)
        self.assertEqual(monitoring_admin_site.name, "monitoring_admin")

    @patch("apps.monitoring.admin_auth.authenticate")
    @patch("apps.monitoring.admin_auth.login")
    def test_login_success_staff_user(self, mock_login, mock_authenticate):
        """Test successful login for staff user."""
        # Mock authentication to return our test user
        mock_authenticate.return_value = self.test_user

        request = self.factory.post("/admin/login/", {"username": "test@example.com", "password": "testpass"})
        request.GET = {}  # Mock GET parameters

        response = self.admin_site.login(request)

        # Should redirect to admin index
        self.assertIsInstance(response, HttpResponseRedirect)
        mock_authenticate.assert_called_once_with(request, username="test@example.com", password="testpass")
        mock_login.assert_called_once_with(request, self.test_user)

    @patch("apps.monitoring.admin_auth.authenticate")
    @patch("apps.monitoring.admin_auth.login")
    def test_login_success_superuser(self, mock_login, mock_authenticate):
        """Test successful login for superuser."""
        # Make user a superuser but not staff
        self.test_user.is_staff = False
        self.test_user.is_superuser = True
        self.test_user.save()

        mock_authenticate.return_value = self.test_user

        request = self.factory.post("/admin/login/", {"username": "test@example.com", "password": "testpass"})
        request.GET = {}

        response = self.admin_site.login(request)

        self.assertIsInstance(response, HttpResponseRedirect)
        mock_login.assert_called_once_with(request, self.test_user)

    @patch("apps.monitoring.admin_auth.authenticate")
    def test_login_success_with_next_parameter(self, mock_authenticate):
        """Test successful login redirects to next parameter."""
        mock_authenticate.return_value = self.test_user

        request = self.factory.post("/admin/login/", {"username": "test@example.com", "password": "testpass"})
        request.GET = {"next": "/admin/custom-page/"}

        with patch("apps.monitoring.admin_auth.login"):
            response = self.admin_site.login(request)

        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertEqual(response.url, "/admin/custom-page/")

    @patch("apps.monitoring.admin_auth.authenticate")
    def test_login_inactive_user(self, mock_authenticate):
        """Test login with inactive user."""
        self.test_user.is_active = False
        self.test_user.save()
        mock_authenticate.return_value = self.test_user

        request = self.factory.post("/admin/login/", {"username": "test@example.com", "password": "testpass"})
        request.GET = {}

        with patch.object(self.admin_site, "login", wraps=self.admin_site.login) as mock_super_login:
            mock_super_login.return_value = Mock()  # Mock the parent login response
            response = self.admin_site.login(request, extra_context={})

        # Should call parent login with error message
        mock_super_login.assert_called()
        args, kwargs = mock_super_login.call_args
        self.assertIn("error_message", kwargs["extra_context"])
        self.assertIn("does not have admin privileges", kwargs["extra_context"]["error_message"])

    @patch("apps.monitoring.admin_auth.authenticate")
    def test_login_non_staff_user(self, mock_authenticate):
        """Test login with non-staff user."""
        self.test_user.is_staff = False
        self.test_user.is_superuser = False
        self.test_user.save()
        mock_authenticate.return_value = self.test_user

        request = self.factory.post("/admin/login/", {"username": "test@example.com", "password": "testpass"})
        request.GET = {}

        with patch.object(self.admin_site, "login", wraps=self.admin_site.login) as mock_super_login:
            mock_super_login.return_value = Mock()
            response = self.admin_site.login(request, extra_context={})

        args, kwargs = mock_super_login.call_args
        self.assertIn("error_message", kwargs["extra_context"])
        self.assertIn("does not have admin privileges", kwargs["extra_context"]["error_message"])

    @patch("apps.monitoring.admin_auth.authenticate")
    def test_login_authentication_failed(self, mock_authenticate):
        """Test login with failed authentication."""
        mock_authenticate.return_value = None

        request = self.factory.post("/admin/login/", {"username": "test@example.com", "password": "wrongpass"})
        request.GET = {}

        with patch.object(self.admin_site, "login", wraps=self.admin_site.login) as mock_super_login:
            mock_super_login.return_value = Mock()
            response = self.admin_site.login(request, extra_context={})

        args, kwargs = mock_super_login.call_args
        self.assertIn("error_message", kwargs["extra_context"])
        self.assertIn("Invalid credentials", kwargs["extra_context"]["error_message"])

    def test_login_missing_username(self):
        """Test login with missing username."""
        request = self.factory.post("/admin/login/", {"password": "testpass"})
        request.GET = {}

        with patch.object(self.admin_site, "login", wraps=self.admin_site.login) as mock_super_login:
            mock_super_login.return_value = Mock()
            response = self.admin_site.login(request)

        # Should call parent login without authentication attempt
        mock_super_login.assert_called()

    def test_login_missing_password(self):
        """Test login with missing password."""
        request = self.factory.post("/admin/login/", {"username": "test@example.com"})
        request.GET = {}

        with patch.object(self.admin_site, "login", wraps=self.admin_site.login) as mock_super_login:
            mock_super_login.return_value = Mock()
            response = self.admin_site.login(request)

        mock_super_login.assert_called()

    def test_login_get_request(self):
        """Test login with GET request."""
        request = self.factory.get("/admin/login/")
        request.GET = {}

        with patch.object(self.admin_site, "login", wraps=self.admin_site.login) as mock_super_login:
            mock_super_login.return_value = Mock()
            response = self.admin_site.login(request)

        # Should call parent login directly
        mock_super_login.assert_called()

    @patch("apps.monitoring.admin_auth.authenticate")
    def test_login_preserves_existing_extra_context(self, mock_authenticate):
        """Test that login preserves existing extra_context."""
        mock_authenticate.return_value = None

        request = self.factory.post("/admin/login/", {"username": "test@example.com", "password": "wrongpass"})
        request.GET = {}

        existing_context = {"existing_key": "existing_value"}

        with patch.object(self.admin_site, "login", wraps=self.admin_site.login) as mock_super_login:
            mock_super_login.return_value = Mock()
            response = self.admin_site.login(request, extra_context=existing_context)

        args, kwargs = mock_super_login.call_args
        self.assertIn("existing_key", kwargs["extra_context"])
        self.assertEqual(kwargs["extra_context"]["existing_key"], "existing_value")
        self.assertIn("error_message", kwargs["extra_context"])


class AuthServiceUserAdminTest(TestCase):
    """Tests for AuthServiceUserAdmin class."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user_admin = AuthServiceUserAdmin(User, monitoring_admin_site)

        # Create test user
        self.test_user = User.objects.create_user(
            username="test@example.com", email="test@example.com", first_name="Test", last_name="User", is_staff=True
        )

    def test_list_display(self):
        """Test that list_display is configured correctly."""
        expected_fields = ["username", "email", "first_name", "last_name", "is_staff", "is_superuser", "last_login"]
        self.assertEqual(self.user_admin.list_display, expected_fields)

    def test_list_filter(self):
        """Test that list_filter is configured correctly."""
        expected_filters = ["is_staff", "is_superuser", "is_active"]
        self.assertEqual(self.user_admin.list_filter, expected_filters)

    def test_search_fields(self):
        """Test that search_fields is configured correctly."""
        expected_fields = ["username", "email", "first_name", "last_name"]
        self.assertEqual(self.user_admin.search_fields, expected_fields)

    def test_readonly_fields(self):
        """Test that readonly_fields is configured correctly."""
        expected_fields = ["username", "email", "last_login", "date_joined"]
        self.assertEqual(self.user_admin.readonly_fields, expected_fields)

    def test_fieldsets(self):
        """Test that fieldsets are configured correctly."""
        expected_fieldsets = (
            (None, {"fields": ("username", "email")}),
            ("Personal info", {"fields": ("first_name", "last_name")}),
            ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser")}),
            ("Important dates", {"fields": ("last_login", "date_joined")}),
        )
        self.assertEqual(self.user_admin.fieldsets, expected_fieldsets)

    def test_has_add_permission_false(self):
        """Test that add permission is disabled."""
        request = self.factory.get("/admin/auth/user/add/")
        self.assertFalse(self.user_admin.has_add_permission(request))

    def test_has_delete_permission_false_without_obj(self):
        """Test that delete permission is disabled without object."""
        request = self.factory.get("/admin/auth/user/")
        self.assertFalse(self.user_admin.has_delete_permission(request))

    def test_has_delete_permission_false_with_obj(self):
        """Test that delete permission is disabled with object."""
        request = self.factory.get(f"/admin/auth/user/{self.test_user.id}/delete/")
        self.assertFalse(self.user_admin.has_delete_permission(request, obj=self.test_user))

    def test_user_registration_with_monitoring_admin_site(self):
        """Test that User model is registered with monitoring_admin_site."""
        self.assertIn(User, monitoring_admin_site._registry)
        self.assertIsInstance(monitoring_admin_site._registry[User], AuthServiceUserAdmin)
