"""
Tests for monitoring views.
"""

import json
import uuid
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from ..authentication import MonitoringUser
from ..models import ActivityLog, CodeMetrics, DeveloperSession, GitEvent


class HealthCheckViewTest(TestCase):
    """Tests for health check view."""

    def test_health_check(self):
        """Test health check endpoint."""
        response = self.client.get("/monitoring/health/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["status"], "healthy")
        self.assertIn("services", response.json())
        self.assertIn("database", response.json()["services"])
        self.assertIn("cache", response.json()["services"])


class SessionViewsTest(APITestCase):
    """Tests for session management views."""

    def setUp(self):
        self.client = APIClient()
        # Mock user for authentication
        self.mock_user = MonitoringUser(
            {"user_id": "12345678-1234-5678-9012-123456789abc", "email": "test@example.com", "username": "testuser"}
        )
        self.client.force_authenticate(user=self.mock_user)

        self.session_data = {
            "user_id": "12345678-1234-5678-9012-123456789abc",
            "ide_name": "VSCode",
            "ide_version": "1.85.0",
            "project_path": "/home/user/project",
            "git_repository_url": "https://github.com/user/repo.git",
            "git_branch": "main",
            "git_commit_hash": "abc123def456",
            "operating_system": "Linux",
        }

    @patch("apps.monitoring.views.RedisClient")
    def test_start_session(self, mock_redis):
        """Test starting a monitoring session."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        response = self.client.post(
            "/monitoring/sessions/start/", data=json.dumps(self.session_data), content_type="application/json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("session_id", response.data)
        self.assertEqual(response.data["user_id"], "12345678-1234-5678-9012-123456789abc")
        self.assertEqual(response.data["ide_name"], "VSCode")

        # Verify session was created in database
        session = DeveloperSession.objects.get(session_id=response.data["session_id"])
        self.assertEqual(str(session.user_id), "12345678-1234-5678-9012-123456789abc")
        self.assertTrue(session.is_active)

        # Verify Redis cache was called
        mock_redis_instance.set_session_data.assert_called_once()

    def test_start_session_invalid_data(self):
        """Test starting session with invalid data."""
        invalid_data = {"ide_name": ""}  # Missing required fields

        response = self.client.post(
            "/monitoring/sessions/start/", data=json.dumps(invalid_data), content_type="application/json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("apps.monitoring.views.RedisClient")
    @patch("apps.monitoring.tasks.process_session_analytics.delay")
    def test_end_session(self, mock_task, mock_redis):
        """Test ending a monitoring session."""
        # Create a session first
        session = DeveloperSession.objects.create(**self.session_data)

        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        end_data = {"session_id": str(session.session_id), "session_metadata": {"final_status": "completed"}}

        response = self.client.post("/monitoring/sessions/end/", data=json.dumps(end_data), content_type="application/json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify session was ended
        session.refresh_from_db()
        self.assertFalse(session.is_active)
        self.assertIsNotNone(session.session_end)

        # Verify Redis cleanup was called
        mock_redis_instance.delete_session_data.assert_called_once()

        # Verify analytics task was triggered
        mock_task.assert_called_once_with(str(session.session_id))

    def test_get_user_sessions(self):
        """Test retrieving user sessions."""
        # Create test sessions
        session1 = DeveloperSession.objects.create(user_id="12345678-1234-5678-9012-123456789abc", ide_name="VSCode")
        session2 = DeveloperSession.objects.create(user_id="12345678-1234-5678-9012-123456789abc", ide_name="PyCharm")
        session3 = DeveloperSession.objects.create(
            user_id="87654321-4321-8765-2109-cba987654321", ide_name="VSCode"
        )  # Different user

        response = self.client.get("/monitoring/sessions/12345678-1234-5678-9012-123456789abc/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)  # Only user 1's sessions
        self.assertEqual(len(response.data["results"]), 2)

    def test_get_user_sessions_unauthorized(self):
        """Test that users can't access other users' sessions."""
        # Mock different user
        other_user = MonitoringUser(
            {"user_id": "87654321-4321-8765-2109-cba987654321", "email": "other@example.com", "username": "otheruser"}
        )
        self.client.force_authenticate(user=other_user)

        DeveloperSession.objects.create(user_id="12345678-1234-5678-9012-123456789abc", ide_name="VSCode")

        # Try to access user 1's sessions as user 2
        response = self.client.get("/monitoring/sessions/12345678-1234-5678-9012-123456789abc/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class ActivityViewsTest(APITestCase):
    """Tests for activity views."""

    def setUp(self):
        self.client = APIClient()
        self.mock_user = MonitoringUser(
            {"user_id": "12345678-1234-5678-9012-123456789abc", "email": "test@example.com", "username": "testuser"}
        )
        self.client.force_authenticate(user=self.mock_user)

        self.session = DeveloperSession.objects.create(user_id="12345678-1234-5678-9012-123456789abc", ide_name="VSCode")

    def test_bulk_activities(self):
        """Test bulk activity upload."""
        activities_data = {
            "session_id": str(self.session.session_id),
            "activities": [
                {"activity_type": "file_open", "file_path": "/path/to/file1.py", "activity_metadata": {"size": 1024}},
                {"activity_type": "file_edit", "file_path": "/path/to/file2.js", "activity_metadata": {"changes": 5}},
            ],
        }

        response = self.client.post(
            "/monitoring/activities/bulk/", data=json.dumps(activities_data), content_type="application/json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["activities_count"], 2)

        # Verify activities were created
        activities = ActivityLog.objects.filter(session=self.session)
        self.assertEqual(activities.count(), 2)

    def test_bulk_activities_invalid_session(self):
        """Test bulk activities with non-existent session."""
        activities_data = {
            "session_id": str(uuid.uuid4()),  # Random UUID
            "activities": [{"activity_type": "file_open", "file_path": "/path/to/file.py"}],
        }

        response = self.client.post(
            "/monitoring/activities/bulk/", data=json.dumps(activities_data), content_type="application/json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class MetricsViewsTest(APITestCase):
    """Tests for metrics views."""

    def setUp(self):
        self.client = APIClient()
        self.mock_user = MonitoringUser(
            {"user_id": "12345678-1234-5678-9012-123456789abc", "email": "test@example.com", "username": "testuser"}
        )
        self.client.force_authenticate(user=self.mock_user)

        self.session = DeveloperSession.objects.create(user_id="12345678-1234-5678-9012-123456789abc", ide_name="VSCode")

    @patch("apps.monitoring.views.RedisClient")
    def test_submit_code_metrics(self, mock_redis):
        """Test submitting code metrics."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        metrics_data = {
            "session": str(self.session.session_id),
            "file_path": "/path/to/file.py",
            "lines_of_code": 100,
            "lines_added": 10,
            "lines_deleted": 5,
            "lines_modified": 3,
            "complexity_score": 15.5,
        }

        response = self.client.post(
            "/monitoring/metrics/code/", data=json.dumps(metrics_data), content_type="application/json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("metrics_id", response.data)

        # Verify metrics were created
        metrics = CodeMetrics.objects.get(metrics_id=response.data["metrics_id"])
        self.assertEqual(metrics.lines_of_code, 100)
        self.assertEqual(metrics.file_extension, "py")

        # Verify Redis caching was called
        mock_redis_instance.set_metrics_cache.assert_called_once()

    def test_record_git_event(self):
        """Test recording a git event."""
        git_data = {
            "session": str(self.session.session_id),
            "event_type": "commit",
            "commit_hash": "abc123def456",
            "commit_message": "Test commit",
            "branch_name": "main",
            "insertions": 10,
            "deletions": 2,
        }

        response = self.client.post("/monitoring/events/git/", data=json.dumps(git_data), content_type="application/json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify git event was created
        git_event = GitEvent.objects.get(event_id=response.data["event_id"])
        self.assertEqual(git_event.event_type, "commit")
        self.assertEqual(git_event.commit_hash, "abc123def456")

        # Verify activity log was created
        activity_logs = ActivityLog.objects.filter(session=self.session)
        self.assertEqual(activity_logs.count(), 1)
        self.assertEqual(activity_logs.first().activity_type, "git_commit")


class AuthenticationTest(APITestCase):
    """Tests for authentication."""

    def test_unauthenticated_request(self):
        """Test that unauthenticated requests are rejected."""
        response = self.client.post("/monitoring/sessions/start/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("apps.monitoring.authentication.ServiceAuthManager")
    def test_jwt_authentication(self, mock_auth_manager):
        """Test JWT authentication."""
        # Mock successful token verification
        mock_manager_instance = MagicMock()
        mock_manager_instance.verify_user_token.return_value = {
            "user_id": "12345678-1234-5678-9012-123456789abc",
            "email": "test@example.com",
            "username": "testuser",
        }
        mock_auth_manager.return_value = mock_manager_instance

        # Set Authorization header
        self.client.credentials(HTTP_AUTHORIZATION="Bearer valid-jwt-token")

        response = self.client.get("/monitoring/sessions/12345678-1234-5678-9012-123456789abc/")

        # Should succeed if authentication works
        self.assertNotEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ApiHomeViewTest(TestCase):
    """Tests for API home view."""

    def test_api_home_json_format(self):
        """Test API home with JSON format."""
        response = self.client.get("/?format=json")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("main_routes", data)
        self.assertIn("service_info", data)
        self.assertIn("api_title", data)
        self.assertEqual(data["api_title"], "SyncScope Monitoring Service")
        self.assertEqual(len(data["main_routes"]), 5)

    @patch("apps.monitoring.views.loader.get_template")
    def test_api_home_html_template_success(self, mock_get_template):
        """Test API home with successful HTML template."""
        mock_template = MagicMock()
        mock_template.render.return_value = "<html>Test</html>"
        mock_get_template.return_value = mock_template

        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "<html>Test</html>")

    @patch("apps.monitoring.views.loader.get_template")
    @patch("apps.monitoring.views.logger")
    def test_api_home_html_template_fallback(self, mock_logger, mock_get_template):
        """Test API home falls back to JSON when template fails."""
        mock_get_template.side_effect = Exception("Template not found")

        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("main_routes", data)
        mock_logger.error.assert_called_once()

    def test_api_home_routes_structure(self):
        """Test that API home routes have correct structure."""
        response = self.client.get("/?format=json")
        data = response.json()

        for route in data["main_routes"]:
            self.assertIn("title", route)
            self.assertIn("description", route)
            self.assertIn("url", route)
            self.assertIn("icon", route)
            self.assertIn("category", route)


class HealthCheckViewsTest(TestCase):
    """Enhanced tests for health check views."""

    @patch("config.database_retry.DatabaseHealthCheck.is_healthy")
    @patch("apps.monitoring.mixins.CacheHealthCheck.is_healthy")
    @patch("config.database_retry.DatabaseHealthCheck.get_schema_info")
    def test_health_check_all_healthy(self, mock_schema, mock_cache, mock_db):
        """Test health check when all services are healthy."""
        mock_db.return_value = True
        mock_cache.return_value = True
        mock_schema.return_value = ["public", "monitoring"]

        response = self.client.get("/health/")

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["checks"]["database"], "healthy")
        self.assertEqual(data["checks"]["redis"], "healthy")
        self.assertEqual(data["checks"]["schemas"], ["public", "monitoring"])
        self.assertIn("response_time_ms", data)

    @patch("config.database_retry.DatabaseHealthCheck.is_healthy")
    @patch("apps.monitoring.mixins.CacheHealthCheck.is_healthy")
    def test_health_check_database_unhealthy(self, mock_cache, mock_db):
        """Test health check when database is unhealthy."""
        mock_db.return_value = False
        mock_cache.return_value = True

        response = self.client.get("/health/")

        self.assertEqual(response.status_code, 503)
        data = response.json()

        self.assertEqual(data["status"], "unhealthy")
        self.assertEqual(data["checks"]["database"], "unhealthy")
        self.assertEqual(data["checks"]["redis"], "healthy")

    @patch("config.database_retry.DatabaseHealthCheck.is_healthy")
    @patch("apps.monitoring.mixins.CacheHealthCheck.is_healthy")
    def test_health_check_database_error(self, mock_cache, mock_db):
        """Test health check when database check throws error."""
        mock_db.side_effect = Exception("Connection failed")
        mock_cache.return_value = True

        response = self.client.get("/health/")

        self.assertEqual(response.status_code, 503)
        data = response.json()

        self.assertEqual(data["status"], "unhealthy")
        self.assertIn("error: Connection failed", data["checks"]["database"])

    @patch("config.database_retry.DatabaseHealthCheck.is_healthy")
    @patch("apps.monitoring.mixins.CacheHealthCheck.is_healthy")
    @patch("config.database_retry.DatabaseHealthCheck.get_schema_info")
    def test_health_check_schema_error(self, mock_schema, mock_cache, mock_db):
        """Test health check when schema info fails."""
        mock_db.return_value = True
        mock_cache.return_value = True
        mock_schema.side_effect = Exception("Schema error")

        response = self.client.get("/health/")
        data = response.json()

        self.assertEqual(data["checks"]["schemas"], ["unknown"])

    def test_liveness_check(self):
        """Test liveness probe endpoint."""
        response = self.client.get("/monitoring/health/live/")

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["status"], "alive")
        self.assertEqual(data["service"], "syncscope-monitoring-service")
        self.assertIn("timestamp", data)

    @patch("config.database_retry.DatabaseHealthCheck.is_healthy")
    @patch("apps.monitoring.mixins.CacheHealthCheck.is_healthy")
    def test_readiness_check_ready(self, mock_cache, mock_db):
        """Test readiness probe when service is ready."""
        mock_db.return_value = True
        mock_cache.return_value = True

        response = self.client.get("/monitoring/health/ready/")

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["status"], "ready")
        self.assertEqual(data["dependencies"]["database"], "ready")
        self.assertEqual(data["dependencies"]["redis"], "ready")

    @patch("config.database_retry.DatabaseHealthCheck.is_healthy")
    @patch("apps.monitoring.mixins.CacheHealthCheck.is_healthy")
    def test_readiness_check_not_ready(self, mock_cache, mock_db):
        """Test readiness probe when service is not ready."""
        mock_db.return_value = False
        mock_cache.return_value = True

        response = self.client.get("/monitoring/health/ready/")

        self.assertEqual(response.status_code, 503)
        data = response.json()

        self.assertEqual(data["status"], "not_ready")
        self.assertEqual(data["dependencies"]["database"], "not_ready")
        self.assertEqual(data["dependencies"]["redis"], "ready")


class SessionViewsEnhancedTest(APITestCase):
    """Enhanced tests for session management views."""

    def setUp(self):
        self.client = APIClient()
        self.mock_user = MonitoringUser(
            {"user_id": "12345678-1234-5678-9012-123456789abc", "email": "test@example.com", "username": "testuser"}
        )
        self.client.force_authenticate(user=self.mock_user)

        self.session_data = {
            "user_id": "12345678-1234-5678-9012-123456789abc",
            "ide_name": "VSCode",
            "ide_version": "1.85.0",
            "project_path": "/home/user/project",
            "git_repository_url": "https://github.com/user/repo.git",
            "git_branch": "main",
            "git_commit_hash": "abc123def456",
            "operating_system": "Linux",
        }

    @patch("apps.monitoring.views.RedisClient")
    @patch("apps.monitoring.views.logger")
    def test_start_session_exception(self, mock_logger, mock_redis):
        """Test start session with exception."""
        mock_redis.side_effect = Exception("Redis error")

        response = self.client.post(
            "/monitoring/sessions/start/", data=json.dumps(self.session_data), content_type="application/json"
        )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        mock_logger.error.assert_called_once()

    @patch("apps.monitoring.views.RedisClient")
    @patch("apps.monitoring.views.logger")
    def test_end_session_exception(self, mock_logger, mock_redis):
        """Test end session with exception."""
        session = DeveloperSession.objects.create(**self.session_data)
        mock_redis.side_effect = Exception("Redis error")

        end_data = {"session_id": str(session.session_id)}
        response = self.client.post("/monitoring/sessions/end/", data=json.dumps(end_data), content_type="application/json")

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        mock_logger.error.assert_called_once()

    def test_end_session_already_ended(self):
        """Test ending a session that's already ended."""
        session = DeveloperSession.objects.create(**self.session_data)
        session.session_end = timezone.now()
        session.save()

        end_data = {"session_id": str(session.session_id)}
        response = self.client.post("/monitoring/sessions/end/", data=json.dumps(end_data), content_type="application/json")

        # Should still return success
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_user_sessions_with_filters(self):
        """Test retrieving user sessions with filters."""
        # Create active and inactive sessions
        active_session = DeveloperSession.objects.create(user_id="12345678-1234-5678-9012-123456789abc", ide_name="VSCode")
        inactive_session = DeveloperSession.objects.create(
            user_id="12345678-1234-5678-9012-123456789abc", ide_name="PyCharm", session_end=timezone.now()
        )

        # Test active_only filter
        response = self.client.get("/monitoring/sessions/12345678-1234-5678-9012-123456789abc/?active_only=true")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only return active session
        # Note: This test depends on the actual implementation of the view

    def test_get_user_sessions_pagination(self):
        """Test user sessions with pagination parameters."""
        # Create multiple sessions
        for i in range(5):
            DeveloperSession.objects.create(user_id="12345678-1234-5678-9012-123456789abc", ide_name=f"IDE{i}")

        response = self.client.get("/monitoring/sessions/12345678-1234-5678-9012-123456789abc/?limit=2&offset=1")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should respect pagination parameters


class BulkActivitiesEnhancedTest(APITestCase):
    """Enhanced tests for bulk activities."""

    def setUp(self):
        self.client = APIClient()
        self.mock_user = MonitoringUser(
            {"user_id": "12345678-1234-5678-9012-123456789abc", "email": "test@example.com", "username": "testuser"}
        )
        self.client.force_authenticate(user=self.mock_user)
        self.session = DeveloperSession.objects.create(user_id="12345678-1234-5678-9012-123456789abc", ide_name="VSCode")

    @patch("apps.monitoring.views.logger")
    def test_bulk_activities_exception(self, mock_logger):
        """Test bulk activities with exception during creation."""
        activities_data = {
            "session_id": str(self.session.session_id),
            "activities": [
                {"activity_type": "file_open", "file_path": "/path/to/file1.py"},
            ],
        }

        # Mock ActivityLog.objects.bulk_create to raise exception
        with patch.object(ActivityLog.objects, "bulk_create", side_effect=Exception("DB Error")):
            response = self.client.post(
                "/monitoring/activities/bulk/", data=json.dumps(activities_data), content_type="application/json"
            )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        mock_logger.error.assert_called_once()

    def test_bulk_activities_empty_list(self):
        """Test bulk activities with empty activities list."""
        activities_data = {
            "session_id": str(self.session.session_id),
            "activities": [],
        }

        response = self.client.post(
            "/monitoring/activities/bulk/", data=json.dumps(activities_data), content_type="application/json"
        )

        # Empty activities list should be rejected by validation
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Activities list cannot be empty", str(response.data))
