"""
Tests for Celery tasks.
"""

import uuid
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone

from apps.monitoring.models import ActivityLog, CodeMetrics, DeveloperSession, GitEvent
from apps.monitoring.tasks import (
    aggregate_user_metrics,
    cleanup_expired_sessions,
    health_check_task,
    process_session_analytics,
)


class ProcessSessionAnalyticsTest(TestCase):
    """Tests for process_session_analytics task."""

    def setUp(self):
        self.session = DeveloperSession.objects.create(
            user_id="12345678-1234-5678-9012-123456789abc", ide_name="VSCode", session_end=timezone.now()  # Completed session
        )

        # Create some related data
        ActivityLog.objects.create(session=self.session, activity_type="file_open", file_path="/path/to/file.py")
        CodeMetrics.objects.create(session=self.session, file_path="/path/to/file.py", lines_of_code=100)
        GitEvent.objects.create(session=self.session, event_type="commit", commit_hash="abc123")

    def test_process_session_analytics_success(self):
        """Test successful session analytics processing."""
        result = process_session_analytics(str(self.session.session_id))

        # Refresh session from database
        self.session.refresh_from_db()

        # Check that analytics data was added to metadata
        self.assertIn("analytics", self.session.session_metadata)
        analytics = self.session.session_metadata["analytics"]

        self.assertEqual(analytics["activities_count"], 1)
        self.assertEqual(analytics["code_metrics_count"], 1)
        self.assertEqual(analytics["git_events_count"], 1)
        self.assertIn("processed_at", analytics)

        self.assertIn("Processed analytics", result)

    def test_process_session_analytics_not_found(self):
        """Test processing analytics for non-existent session."""
        fake_session_id = str(uuid.uuid4())
        result = process_session_analytics(fake_session_id)

        self.assertIn("not found", result)


class CleanupExpiredSessionsTest(TestCase):
    """Tests for cleanup_expired_sessions task."""

    def setUp(self):
        # Create expired session (older than 24 hours, still active)
        old_time = timezone.now() - timedelta(hours=25)
        self.expired_session = DeveloperSession.objects.create(
            user_id="12345678-1234-5678-9012-123456789abc", ide_name="VSCode", session_start=old_time, session_end=None  # Still active
        )

        # Create recent session (should not be cleaned up)
        recent_time = timezone.now() - timedelta(hours=1)
        self.recent_session = DeveloperSession.objects.create(
            user_id=2, ide_name="PyCharm", session_start=recent_time, session_end=None  # Still active
        )

        # Create already ended session (should not be cleaned up)
        self.ended_session = DeveloperSession.objects.create(
            user_id=3, ide_name="Vim", session_start=old_time, session_end=old_time + timedelta(hours=1)  # Already ended
        )

    @patch("apps.monitoring.tasks.RedisClient")
    def test_cleanup_expired_sessions(self, mock_redis):
        """Test cleanup of expired sessions."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        result = cleanup_expired_sessions()

        # Refresh sessions from database
        self.expired_session.refresh_from_db()
        self.recent_session.refresh_from_db()
        self.ended_session.refresh_from_db()

        # Check that only expired session was ended
        self.assertIsNotNone(self.expired_session.session_end)  # Should be ended
        self.assertIsNone(self.recent_session.session_end)  # Should still be active
        self.assertIsNotNone(self.ended_session.session_end)  # Should remain ended

        # Check Redis cleanup was called
        mock_redis_instance.delete_session_data.assert_called_once()

        self.assertIn("Cleaned up 1 expired sessions", result)


class AggregateUserMetricsTest(TestCase):
    """Tests for aggregate_user_metrics task."""

    def setUp(self):
        # Create sessions for today
        today = timezone.now().date()
        start_of_day = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))

        self.session1 = DeveloperSession.objects.create(
            user_id="12345678-1234-5678-9012-123456789abc",
            ide_name="VSCode",
            session_start=start_of_day + timedelta(hours=1),
            session_end=start_of_day + timedelta(hours=2),
            session_duration_minutes=60,
        )

        self.session2 = DeveloperSession.objects.create(
            user_id="12345678-1234-5678-9012-123456789abc",
            ide_name="PyCharm",
            session_start=start_of_day + timedelta(hours=3),
            session_end=start_of_day + timedelta(hours=4),
            session_duration_minutes=60,
        )

        # Create related data
        ActivityLog.objects.create(session=self.session1, activity_type="file_open", file_path="/path/to/file.py")

        CodeMetrics.objects.create(
            session=self.session1, file_path="/path/to/file.py", lines_of_code=100, complexity_score=10.5
        )

    @patch("apps.monitoring.tasks.RedisClient")
    def test_aggregate_user_metrics(self, mock_redis):
        """Test user metrics aggregation."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        today = timezone.now().date()
        result = aggregate_user_metrics(1, today)

        # Check that Redis caching was called
        mock_redis_instance.set_metrics_cache.assert_called_once()

        # Check the cached data structure
        call_args = mock_redis_instance.set_metrics_cache.call_args[0]
        cache_key, cached_data = call_args[0], call_args[1]

        self.assertIn("user_metrics:1:", cache_key)
        self.assertEqual(cached_data["user_id"], 1)
        self.assertEqual(cached_data["sessions_count"], 2)
        self.assertEqual(cached_data["total_duration_minutes"], 120)  # 60 + 60
        self.assertEqual(cached_data["activities_count"], 1)
        self.assertEqual(cached_data["code_metrics_count"], 1)
        self.assertEqual(cached_data["total_lines_of_code"], 100)
        self.assertEqual(float(cached_data["avg_complexity_score"]), 10.5)

        self.assertIn("Aggregated metrics", result)

    @patch("apps.monitoring.tasks.RedisClient")
    def test_aggregate_user_metrics_no_sessions(self, mock_redis):
        """Test aggregation when user has no sessions."""
        result = aggregate_user_metrics(999, timezone.now().date())  # Non-existent user

        self.assertIn("No sessions found", result)


class HealthCheckTaskTest(TestCase):
    """Tests for health_check_task."""

    @patch("apps.monitoring.tasks.RedisClient")
    @patch("apps.monitoring.tasks.DatabaseManager")
    def test_health_check_success(self, mock_db_manager, mock_redis):
        """Test successful health check."""
        # Mock successful database connection
        mock_db_manager.test_connection.return_value = True

        # Mock successful Redis connection
        mock_redis_instance = MagicMock()
        mock_redis_instance.redis_client.ping.return_value = True
        mock_redis.return_value = mock_redis_instance

        result = health_check_task()

        self.assertTrue(result["database"])
        self.assertTrue(result["redis"])
        self.assertTrue(result["overall"])

    @patch("apps.monitoring.tasks.RedisClient")
    @patch("apps.monitoring.tasks.DatabaseManager")
    def test_health_check_database_failure(self, mock_db_manager, mock_redis):
        """Test health check with database failure."""
        # Mock database connection failure
        mock_db_manager.test_connection.return_value = False

        # Mock successful Redis connection
        mock_redis_instance = MagicMock()
        mock_redis_instance.redis_client.ping.return_value = True
        mock_redis.return_value = mock_redis_instance

        result = health_check_task()

        self.assertFalse(result["database"])
        self.assertTrue(result["redis"])
        self.assertFalse(result["overall"])  # Overall should fail if any component fails

    @patch("apps.monitoring.tasks.RedisClient")
    @patch("apps.monitoring.tasks.DatabaseManager")
    def test_health_check_redis_failure(self, mock_db_manager, mock_redis):
        """Test health check with Redis failure."""
        # Mock successful database connection
        mock_db_manager.test_connection.return_value = True

        # Mock Redis connection failure
        mock_redis_instance = MagicMock()
        mock_redis_instance.redis_client.ping.side_effect = Exception("Redis connection failed")
        mock_redis.return_value = mock_redis_instance

        result = health_check_task()

        self.assertTrue(result["database"])
        self.assertFalse(result["redis"])
        self.assertFalse(result["overall"])  # Overall should fail if any component fails

    @patch("apps.monitoring.tasks.RedisClient")
    @patch("apps.monitoring.tasks.DatabaseManager")
    def test_health_check_exception(self, mock_db_manager, mock_redis):
        """Test health check with unexpected exception."""
        # Mock database manager raising exception
        mock_db_manager.test_connection.side_effect = Exception("Unexpected error")

        result = health_check_task()

        self.assertIn("error", result)
        self.assertEqual(result["overall"], False)
