"""
Tests for monitoring views.
"""

import json
import uuid
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.monitoring.authentication import MonitoringUser
from apps.monitoring.models import ActivityLog, CodeMetrics, DeveloperSession, GitEvent


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
        self.mock_user = MonitoringUser({"user_id": "12345678-1234-5678-9012-123456789abc", "email": "test@example.com", "username": "testuser"})
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
        self.assertEqual(response.data["user_id"], 1)
        self.assertEqual(response.data["ide_name"], "VSCode")

        # Verify session was created in database
        session = DeveloperSession.objects.get(session_id=response.data["session_id"])
        self.assertEqual(session.user_id, 1)
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
        session3 = DeveloperSession.objects.create(user_id=2, ide_name="VSCode")  # Different user

        response = self.client.get("/monitoring/sessions/1/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)  # Only user 1's sessions
        self.assertEqual(len(response.data["results"]), 2)

    def test_get_user_sessions_unauthorized(self):
        """Test that users can't access other users' sessions."""
        # Mock different user
        other_user = MonitoringUser({"user_id": "87654321-4321-8765-2109-cba987654321", "email": "other@example.com", "username": "otheruser"})
        self.client.force_authenticate(user=other_user)

        DeveloperSession.objects.create(user_id="12345678-1234-5678-9012-123456789abc", ide_name="VSCode")

        # Try to access user 1's sessions as user 2
        response = self.client.get("/monitoring/sessions/1/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class ActivityViewsTest(APITestCase):
    """Tests for activity views."""

    def setUp(self):
        self.client = APIClient()
        self.mock_user = MonitoringUser({"user_id": 1, "email": "test@example.com", "username": "testuser"})
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
        self.mock_user = MonitoringUser({"user_id": 1, "email": "test@example.com", "username": "testuser"})
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
            "user_id": 1,
            "email": "test@example.com",
            "username": "testuser",
        }
        mock_auth_manager.return_value = mock_manager_instance

        # Set Authorization header
        self.client.credentials(HTTP_AUTHORIZATION="Bearer valid-jwt-token")

        response = self.client.get("/monitoring/sessions/1/")

        # Should succeed if authentication works
        self.assertNotEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
