"""
Tests for class_views module.
"""

from unittest.mock import MagicMock, Mock, patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.monitoring.authentication import MonitoringUser
from apps.monitoring.class_views import BaseMonitoringAPIView, HealthMetricsView, SessionStatsView
from apps.monitoring.models import DeveloperSession
from config.database_retry import DatabaseHealthCheck


class BaseMonitoringAPIViewTest(APITestCase):
    """Tests for BaseMonitoringAPIView class."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.mock_user = MonitoringUser(
            {"user_id": "12345678-1234-5678-9012-123456789abc", "email": "test@example.com", "username": "testuser"}
        )

    def test_permission_classes(self):
        """Test that BaseMonitoringAPIView has correct permission classes."""
        view = BaseMonitoringAPIView()
        self.assertEqual(len(view.permission_classes), 1)
        self.assertEqual(view.permission_classes[0].__name__, "IsAuthenticated")

    def test_inheritance(self):
        """Test that BaseMonitoringAPIView inherits from correct mixins."""
        view = BaseMonitoringAPIView()

        # Check that it has methods from mixins and base classes
        self.assertTrue(hasattr(view, "dispatch"))  # From PerformanceMonitoringMixin or APIView
        # Check MRO to verify inheritance chain
        mro_classes = [cls.__name__ for cls in BaseMonitoringAPIView.__mro__]
        self.assertIn("ServerlessViewMixin", mro_classes)
        self.assertIn("PerformanceMonitoringMixin", mro_classes)
        self.assertIn("APIView", mro_classes)


class SessionStatsViewTest(APITestCase):
    """Tests for SessionStatsView class."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.mock_user = MonitoringUser(
            {"user_id": "12345678-1234-5678-9012-123456789abc", "email": "test@example.com", "username": "testuser"}
        )
        self.client.force_authenticate(user=self.mock_user)

        # Create test sessions
        self.session1 = DeveloperSession.objects.create(
            user_id="12345678-1234-5678-9012-123456789abc",
            ide_name="VSCode",
            session_duration_minutes=30,
            session_start=timezone.now() - timezone.timedelta(hours=2),
            session_end=timezone.now() - timezone.timedelta(hours=1, minutes=30),
        )

        self.session2 = DeveloperSession.objects.create(
            user_id="12345678-1234-5678-9012-123456789abc",
            ide_name="PyCharm",
            session_duration_minutes=45,
            session_start=timezone.now() - timezone.timedelta(hours=1),
            session_end=timezone.now() - timezone.timedelta(minutes=15),
        )

        # Active session (no end time)
        self.active_session = DeveloperSession.objects.create(
            user_id="12345678-1234-5678-9012-123456789abc",
            ide_name="IntelliJ",
            session_start=timezone.now() - timezone.timedelta(minutes=30),
        )

        # Different user session (should not appear in stats)
        self.other_user_session = DeveloperSession.objects.create(
            user_id="87654321-4321-8765-2109-cba987654321", ide_name="VSCode", session_duration_minutes=20
        )

    def test_permission_classes(self):
        """Test that SessionStatsView has correct permission classes."""
        view = SessionStatsView()
        self.assertEqual(len(view.permission_classes), 1)
        self.assertEqual(view.permission_classes[0].__name__, "CanAccessUserData")

    def test_get_session_stats_success(self):
        """Test successful session stats retrieval."""
        response = self.client.get("/monitoring/sessions/12345678-1234-5678-9012-123456789abc/stats/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        self.assertEqual(str(data["user_id"]), "12345678-1234-5678-9012-123456789abc")
        self.assertEqual(data["total_sessions"], 3)  # 2 completed + 1 active
        self.assertEqual(data["active_sessions"], 1)
        self.assertEqual(data["total_duration_hours"], 1.2)  # (30 + 45) / 60 = 1.25, rounded to 1.2
        self.assertEqual(data["avg_session_duration_minutes"], 37.5)  # (30 + 45) / 2
        self.assertIsNotNone(data["last_session"])
        self.assertIsNotNone(data["generated_at"])

    def test_get_session_stats_no_sessions(self):
        """Test session stats for user with no sessions."""
        # Create a different user
        other_user = MonitoringUser(
            {"user_id": "99999999-9999-9999-9999-999999999999", "email": "other@example.com", "username": "otheruser"}
        )
        self.client.force_authenticate(user=other_user)

        response = self.client.get("/monitoring/sessions/99999999-9999-9999-9999-999999999999/stats/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        self.assertEqual(str(data["user_id"]), "99999999-9999-9999-9999-999999999999")
        self.assertEqual(data["total_sessions"], 0)
        self.assertEqual(data["active_sessions"], 0)
        self.assertEqual(data["total_duration_hours"], 0.0)
        self.assertEqual(data["avg_session_duration_minutes"], 0.0)
        self.assertIsNone(data["last_session"])

    def test_get_session_stats_only_active_sessions(self):
        """Test session stats when user has only active sessions."""
        # Delete completed sessions
        DeveloperSession.objects.filter(user_id="12345678-1234-5678-9012-123456789abc", session_end__isnull=False).delete()

        response = self.client.get("/monitoring/sessions/12345678-1234-5678-9012-123456789abc/stats/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        self.assertEqual(data["total_sessions"], 1)
        self.assertEqual(data["active_sessions"], 1)
        self.assertEqual(data["total_duration_hours"], 0.0)  # Active sessions have no duration yet
        self.assertEqual(data["avg_session_duration_minutes"], 0.0)

    def test_get_session_stats_unauthorized_user(self):
        """Test that users can't access other users' stats."""
        other_user = MonitoringUser(
            {"user_id": "87654321-4321-8765-2109-cba987654321", "email": "other@example.com", "username": "otheruser"}
        )
        self.client.force_authenticate(user=other_user)

        # Try to access user 1's stats as user 2
        response = self.client.get("/monitoring/sessions/12345678-1234-5678-9012-123456789abc/stats/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_session_stats_unauthenticated(self):
        """Test that unauthenticated users can't access stats."""
        self.client.force_authenticate(user=None)

        response = self.client.get("/monitoring/sessions/12345678-1234-5678-9012-123456789abc/stats/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("apps.monitoring.class_views.DeveloperSession.objects")
    def test_get_session_stats_database_error(self, mock_sessions):
        """Test handling of database errors during stats retrieval."""
        mock_sessions.filter.side_effect = Exception("Database error")

        # This should raise the exception since it's not handled in the view
        with self.assertRaises(Exception):
            self.client.get("/monitoring/sessions/12345678-1234-5678-9012-123456789abc/stats/")


class HealthMetricsViewTest(APITestCase):
    """Tests for HealthMetricsView class."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()

    def test_permission_classes_allow_unauthenticated(self):
        """Test that HealthMetricsView allows unauthenticated access."""
        view = HealthMetricsView()
        self.assertEqual(view.permission_classes, [])

    def test_unauthenticated_access_allowed(self):
        """Test that unauthenticated users can access health metrics."""
        with (
            patch("apps.monitoring.class_views.DatabaseHealthCheck.is_healthy") as mock_db_healthy,
            patch("apps.monitoring.class_views.CacheHealthCheck.is_healthy") as mock_cache_healthy,
            patch("psutil.virtual_memory") as mock_memory,
            patch("psutil.cpu_percent") as mock_cpu,
            patch("psutil.disk_usage") as mock_disk,
        ):
            mock_db_healthy.return_value = True
            mock_cache_healthy.return_value = True
            mock_memory.return_value = Mock(percent=45.0)
            mock_cpu.return_value = 12.0
            mock_disk.return_value = Mock(percent=60.0)

            response = self.client.get("/monitoring/health/metrics/")

            self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch("apps.monitoring.class_views.DatabaseHealthCheck.is_healthy")
    @patch("apps.monitoring.class_views.CacheHealthCheck.is_healthy")
    @patch("psutil.virtual_memory")
    @patch("psutil.cpu_percent")
    @patch("psutil.disk_usage")
    @patch("os.getpid")
    def test_get_health_metrics_all_healthy(
        self, mock_getpid, mock_disk, mock_cpu, mock_memory, mock_cache_healthy, mock_db_healthy
    ):
        """Test successful health metrics retrieval when all services are healthy."""
        # Mock all dependencies
        mock_db_healthy.return_value = True
        mock_cache_healthy.return_value = True
        mock_memory.return_value = Mock(percent=45.0)
        mock_cpu.return_value = 12.0
        mock_disk.return_value = Mock(percent=60.0)
        mock_getpid.return_value = 12345

        response = self.client.get("/monitoring/health/metrics/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        self.assertEqual(data["service"], "syncscope-monitoring-service")
        self.assertEqual(data["status"], "healthy")
        self.assertIn("version", data)
        self.assertIn("timestamp", data)
        self.assertIn("response_time_ms", data)

        # Check database status
        self.assertEqual(data["database"]["status"], "healthy")
        self.assertIn("response_time_ms", data["database"])

        # Check redis status
        self.assertEqual(data["redis"]["status"], "healthy")
        self.assertIn("response_time_ms", data["redis"])

        # Check system metrics
        self.assertEqual(data["system"]["memory_usage"], "45.0%")
        self.assertEqual(data["system"]["cpu_usage"], "12.0%")
        self.assertEqual(data["system"]["disk_usage"], "60.0%")

        # Check process info
        self.assertEqual(data["process"]["pid"], 12345)
        self.assertIn("python_version", data["process"])
        self.assertIn("django_version", data["process"])

    def test_get_health_metrics_basic_structure(self):
        """Test that health metrics endpoint returns expected structure."""
        response = self.client.get("/monitoring/health/metrics/")

        # Should get a response (may be 200 or 503 depending on actual health)
        self.assertIn(response.status_code, [200, 503])

        data = response.data
        # Check required fields are present
        self.assertIn("service", data)
        self.assertIn("status", data)
        self.assertIn("timestamp", data)
        self.assertIn("database", data)
        self.assertIn("redis", data)
        self.assertIn("system", data)
        self.assertIn("process", data)

        # Check database and redis have status fields
        self.assertIn("status", data["database"])
        self.assertIn("status", data["redis"])

    @patch("apps.monitoring.class_views.DatabaseHealthCheck.is_healthy")
    @patch("apps.monitoring.class_views.CacheHealthCheck.is_healthy")
    def test_get_health_metrics_redis_unhealthy(self, mock_cache_healthy, mock_db_healthy):
        """Test health metrics when redis is unhealthy."""
        mock_db_healthy.return_value = True
        mock_cache_healthy.return_value = False

        response = self.client.get("/monitoring/health/metrics/")

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

        data = response.data
        self.assertEqual(data["status"], "unhealthy")
        self.assertEqual(data["database"]["status"], "healthy")
        self.assertEqual(data["redis"]["status"], "unhealthy")

    @patch("psutil.virtual_memory")
    @patch("psutil.cpu_percent")
    @patch("psutil.disk_usage")
    def test_get_health_metrics_system_metrics(self, mock_disk, mock_cpu, mock_memory):
        """Test health metrics system information collection."""
        mock_memory.return_value = Mock(percent=75.5)
        mock_cpu.return_value = 25.3
        mock_disk.return_value = Mock(percent=45.8)

        response = self.client.get("/monitoring/health/metrics/")

        self.assertIn(response.status_code, [200, 503])

        data = response.data
        # Check system metrics are present
        if "memory_usage" in data["system"]:
            self.assertEqual(data["system"]["memory_usage"], "75.5%")
            self.assertEqual(data["system"]["cpu_usage"], "25.3%")
            self.assertEqual(data["system"]["disk_usage"], "45.8%")

    @patch("psutil.virtual_memory")
    def test_get_health_metrics_psutil_unavailable(self, mock_memory):
        """Test health metrics when psutil raises ImportError."""
        mock_memory.side_effect = ImportError("psutil not available")

        response = self.client.get("/monitoring/health/metrics/")

        self.assertIn(response.status_code, [200, 503])

        data = response.data
        # Should handle psutil unavailability gracefully
        self.assertIn("system", data)
        if "status" in data["system"]:
            self.assertEqual(data["system"]["status"], "metrics_unavailable")

    @patch("apps.monitoring.class_views.DatabaseHealthCheck.is_healthy")
    @patch("apps.monitoring.class_views.CacheHealthCheck.is_healthy")
    def test_get_health_metrics_redis_exception(self, mock_cache_healthy, mock_db_healthy):
        """Test health metrics when redis check raises exception."""
        mock_db_healthy.return_value = True
        mock_cache_healthy.side_effect = Exception("Redis connection failed")

        response = self.client.get("/monitoring/health/metrics/")

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

        data = response.data
        self.assertEqual(data["status"], "unhealthy")
        self.assertEqual(data["database"]["status"], "healthy")
        self.assertEqual(data["redis"]["status"], "error")
        self.assertIn("error", data["redis"])

    @patch("apps.monitoring.class_views.DatabaseHealthCheck.is_healthy")
    @patch("apps.monitoring.class_views.CacheHealthCheck.is_healthy")
    @patch("psutil.virtual_memory")
    def test_get_health_metrics_psutil_unavailable(self, mock_memory, mock_cache_healthy, mock_db_healthy):
        """Test health metrics when psutil is not available or raises exception."""
        mock_db_healthy.return_value = True
        mock_cache_healthy.return_value = True
        mock_memory.side_effect = ImportError("psutil not available")

        response = self.client.get("/monitoring/health/metrics/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["system"]["status"], "metrics_unavailable")

    @patch("apps.monitoring.class_views.DatabaseHealthCheck.is_healthy")
    @patch("apps.monitoring.class_views.CacheHealthCheck.is_healthy")
    @patch("psutil.virtual_memory")
    @patch("psutil.cpu_percent")
    @patch("psutil.disk_usage")
    def test_get_health_metrics_system_exception(self, mock_disk, mock_cpu, mock_memory, mock_cache_healthy, mock_db_healthy):
        """Test health metrics when system metrics raise exception."""
        mock_db_healthy.return_value = True
        mock_cache_healthy.return_value = True
        mock_memory.side_effect = Exception("System error")

        response = self.client.get("/monitoring/health/metrics/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["system"]["status"], "metrics_unavailable")

    @patch("apps.monitoring.class_views.DatabaseHealthCheck.is_healthy")
    @patch("apps.monitoring.class_views.CacheHealthCheck.is_healthy")
    @override_settings(VERSION="2.1.0", DJANGO_VERSION="4.2.0")
    def test_get_health_metrics_with_custom_versions(self, mock_cache_healthy, mock_db_healthy):
        """Test health metrics with custom version settings."""
        mock_db_healthy.return_value = True
        mock_cache_healthy.return_value = True

        response = self.client.get("/monitoring/health/metrics/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        self.assertEqual(data["version"], "2.1.0")
        self.assertEqual(data["process"]["django_version"], "4.2.0")
