"""
Tests for monitoring models.
"""

import uuid
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.monitoring.models import ActivityLog, CodeMetrics, DeveloperSession, GitEvent


class DeveloperSessionModelTest(TestCase):
    """Tests for DeveloperSession model."""

    def setUp(self):
        self.test_user_id = uuid.UUID("12345678-1234-5678-9012-123456789abc")
        self.session_data = {
            "user_id": self.test_user_id,
            "ide_name": "VSCode",
            "ide_version": "1.85.0",
            "project_path": "/home/user/project",
            "git_repository_url": "https://github.com/user/repo.git",
            "git_branch": "main",
            "git_commit_hash": "abc123def456",
            "operating_system": "Linux",
            "session_metadata": {"theme": "dark"},
        }

    def test_create_session(self):
        """Test creating a developer session."""
        session = DeveloperSession.objects.create(**self.session_data)

        self.assertIsInstance(session.session_id, uuid.UUID)
        self.assertEqual(session.user_id, self.test_user_id)
        self.assertEqual(session.ide_name, "VSCode")
        self.assertTrue(session.is_active)
        self.assertIsNone(session.session_duration_minutes)

    def test_session_duration_calculation(self):
        """Test session duration calculation."""
        session = DeveloperSession.objects.create(**self.session_data)

        # End the session 30 minutes later
        session.session_end = session.session_start + timedelta(minutes=30)
        session.save()

        self.assertEqual(session.session_duration_minutes, 30)
        self.assertFalse(session.is_active)

    def test_end_session_method(self):
        """Test the end_session method."""
        session = DeveloperSession.objects.create(**self.session_data)

        self.assertTrue(session.is_active)

        session.end_session()

        self.assertFalse(session.is_active)
        self.assertIsNotNone(session.session_end)
        self.assertIsNotNone(session.session_duration_minutes)

    def test_string_representation(self):
        """Test string representation of the model."""
        session = DeveloperSession.objects.create(**self.session_data)
        expected = f"Session {session.session_id} - User {self.test_user_id}"
        self.assertEqual(str(session), expected)


class ActivityLogModelTest(TestCase):
    """Tests for ActivityLog model."""

    def setUp(self):
        self.session = DeveloperSession.objects.create(user_id="12345678-1234-5678-9012-123456789abc", ide_name="VSCode")
        self.activity_data = {
            "session": self.session,
            "activity_type": "file_open",
            "file_path": "/path/to/file.py",
            "activity_metadata": {"size": 1024},
        }

    def test_create_activity_log(self):
        """Test creating an activity log."""
        activity = ActivityLog.objects.create(**self.activity_data)

        self.assertIsInstance(activity.log_id, uuid.UUID)
        self.assertEqual(activity.session, self.session)
        self.assertEqual(activity.activity_type, "file_open")
        self.assertEqual(activity.file_extension, "py")

    def test_file_extension_extraction(self):
        """Test automatic file extension extraction."""
        activity = ActivityLog.objects.create(**self.activity_data)
        self.assertEqual(activity.file_extension, "py")

        # Test without extension
        activity2 = ActivityLog.objects.create(session=self.session, activity_type="file_open", file_path="/path/to/README")
        self.assertEqual(activity2.file_extension, "")

    def test_activity_choices(self):
        """Test activity type choices validation."""
        # Valid choice
        activity = ActivityLog.objects.create(**self.activity_data)
        self.assertEqual(activity.activity_type, "file_open")

        # Invalid choice should be handled by form/serializer validation
        # Database doesn't enforce choices by default in Django


class CodeMetricsModelTest(TestCase):
    """Tests for CodeMetrics model."""

    def setUp(self):
        self.session = DeveloperSession.objects.create(user_id="12345678-1234-5678-9012-123456789abc", ide_name="VSCode")
        self.metrics_data = {
            "session": self.session,
            "file_path": "/path/to/file.py",
            "lines_of_code": 100,
            "lines_added": 10,
            "lines_deleted": 5,
            "lines_modified": 3,
            "complexity_score": 15.5,
            "function_count": 5,
            "class_count": 1,
        }

    def test_create_code_metrics(self):
        """Test creating code metrics."""
        metrics = CodeMetrics.objects.create(**self.metrics_data)

        self.assertIsInstance(metrics.metrics_id, uuid.UUID)
        self.assertEqual(metrics.session, self.session)
        self.assertEqual(metrics.lines_of_code, 100)
        self.assertEqual(metrics.file_extension, "py")

    def test_total_changes_property(self):
        """Test total_changes property calculation."""
        metrics = CodeMetrics.objects.create(**self.metrics_data)
        expected_total = 10 + 5 + 3  # added + deleted + modified
        self.assertEqual(metrics.total_changes, expected_total)

    def test_file_extension_extraction(self):
        """Test automatic file extension extraction in save method."""
        metrics = CodeMetrics.objects.create(**self.metrics_data)
        self.assertEqual(metrics.file_extension, "py")


class GitEventModelTest(TestCase):
    """Tests for GitEvent model."""

    def setUp(self):
        self.session = DeveloperSession.objects.create(user_id="12345678-1234-5678-9012-123456789abc", ide_name="VSCode")
        self.git_data = {
            "session": self.session,
            "event_type": "commit",
            "commit_hash": "abc123def456",
            "commit_message": "Initial commit",
            "branch_name": "main",
            "insertions": 100,
            "deletions": 20,
            "author_name": "Test User",
            "author_email": "test@example.com",
        }

    def test_create_git_event(self):
        """Test creating a git event."""
        event = GitEvent.objects.create(**self.git_data)

        self.assertIsInstance(event.event_id, uuid.UUID)
        self.assertEqual(event.session, self.session)
        self.assertEqual(event.event_type, "commit")
        self.assertEqual(event.commit_hash, "abc123def456")

    def test_net_changes_property(self):
        """Test net_changes property calculation."""
        event = GitEvent.objects.create(**self.git_data)
        expected_net = 100 - 20  # insertions - deletions
        self.assertEqual(event.net_changes, expected_net)

    def test_net_changes_with_none_values(self):
        """Test net_changes when insertions/deletions are None."""
        event_data = self.git_data.copy()
        event_data["insertions"] = None
        event_data["deletions"] = None

        event = GitEvent.objects.create(**event_data)
        self.assertIsNone(event.net_changes)

    def test_string_representation(self):
        """Test string representation of git event."""
        event = GitEvent.objects.create(**self.git_data)
        expected = f"commit - abc123def456 - {event.timestamp}"
        self.assertEqual(str(event), expected)
