"""
Tests for Celery tasks.
"""

import uuid
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone

from ..models import ActivityLog, CodeMetrics, DeveloperSession, GitEvent
from ..tasks import aggregate_user_metrics, cleanup_expired_sessions, process_session_analytics


class ProcessSessionAnalyticsTest(TestCase):
    """Tests for process_session_analytics task."""

    def setUp(self):
        self.session = DeveloperSession.objects.create(
            user_id=1, ide_name="VSCode", session_end=timezone.now()  # Completed session
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
            user_id=1, ide_name="VSCode", session_start=old_time, session_end=None  # Still active
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
            user_id=1,
            ide_name="VSCode",
            session_start=start_of_day + timedelta(hours=1),
            session_end=start_of_day + timedelta(hours=2),
            session_duration_minutes=60,
        )

        self.session2 = DeveloperSession.objects.create(
            user_id=1,
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


class ProcessSessionAnalyticsEnhancedTest(TestCase):
    """Enhanced tests for process_session_analytics task."""

    def setUp(self):
        self.session = DeveloperSession.objects.create(user_id=1, ide_name="VSCode", session_end=timezone.now())

    @patch("apps.monitoring.tasks.process_session_analytics.retry")
    def test_process_session_analytics_exception_retry(self, mock_retry):
        """Test task retries on exception."""
        # Mock the task object
        mock_task = MagicMock()
        mock_task.request.retries = 1
        mock_retry.side_effect = Exception("Retry called")

        # Mock session save to raise exception
        with patch.object(DeveloperSession, "save", side_effect=Exception("Database error")):
            with self.assertRaises(Exception):
                # Call the task function directly with mock self
                from apps.monitoring.tasks import process_session_analytics

                process_session_analytics.__wrapped__(mock_task, str(self.session.session_id))

    def test_process_session_analytics_empty_session(self):
        """Test processing analytics for session with no related data."""
        result = process_session_analytics(str(self.session.session_id))

        self.session.refresh_from_db()
        analytics = self.session.session_metadata["analytics"]

        self.assertEqual(analytics["activities_count"], 0)
        self.assertEqual(analytics["code_metrics_count"], 0)
        self.assertEqual(analytics["git_events_count"], 0)
        self.assertIn("processed_at", analytics)


class CleanupExpiredSessionsEnhancedTest(TestCase):
    """Enhanced tests for cleanup_expired_sessions task."""

    @patch("apps.monitoring.tasks.RedisClient")
    @patch("apps.monitoring.tasks.logger")
    def test_cleanup_expired_sessions_exception(self, mock_logger, mock_redis):
        """Test cleanup task with exception."""
        # Mock RedisClient to raise exception
        mock_redis.side_effect = Exception("Redis error")

        with self.assertRaises(Exception):
            cleanup_expired_sessions()

        mock_logger.error.assert_called_once()

    @patch("apps.monitoring.tasks.RedisClient")
    def test_cleanup_no_expired_sessions(self, mock_redis):
        """Test cleanup when no sessions need cleanup."""
        # Create only recent sessions
        recent_time = timezone.now() - timedelta(hours=1)
        DeveloperSession.objects.create(user_id=1, ide_name="VSCode", session_start=recent_time)

        result = cleanup_expired_sessions()
        self.assertIn("Cleaned up 0 expired sessions", result)

    @patch("apps.monitoring.tasks.RedisClient")
    def test_cleanup_multiple_expired_sessions(self, mock_redis):
        """Test cleanup of multiple expired sessions."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        old_time = timezone.now() - timedelta(hours=25)

        # Create multiple expired sessions
        session1 = DeveloperSession.objects.create(user_id=1, ide_name="VSCode", session_start=old_time)
        session2 = DeveloperSession.objects.create(user_id=2, ide_name="PyCharm", session_start=old_time)

        result = cleanup_expired_sessions()

        # Both should be ended
        session1.refresh_from_db()
        session2.refresh_from_db()
        self.assertIsNotNone(session1.session_end)
        self.assertIsNotNone(session2.session_end)

        # Redis cleanup should be called twice
        self.assertEqual(mock_redis_instance.delete_session_data.call_count, 2)
        self.assertIn("Cleaned up 2 expired sessions", result)


class AggregateUserMetricsEnhancedTest(TestCase):
    """Enhanced tests for aggregate_user_metrics task."""

    def setUp(self):
        self.user_id = 999  # Use different user_id to avoid conflicts with other test classes
        today = timezone.now().date()
        start_of_day = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))

        self.session = DeveloperSession.objects.create(
            user_id=self.user_id,
            ide_name="VSCode",
            session_start=start_of_day + timedelta(hours=1),
            session_end=start_of_day + timedelta(hours=2),
            session_duration_minutes=60,
        )

    @patch("apps.monitoring.tasks.aggregate_user_metrics.retry")
    def test_aggregate_user_metrics_exception_retry(self, mock_retry):
        """Test task retries on exception."""
        mock_task = MagicMock()
        mock_task.request.retries = 1
        mock_retry.side_effect = Exception("Retry called")

        # Mock RedisClient to raise exception
        with patch("apps.monitoring.tasks.RedisClient", side_effect=Exception("Redis error")):
            with self.assertRaises(Exception):
                from apps.monitoring.tasks import aggregate_user_metrics

                aggregate_user_metrics.__wrapped__(mock_task, self.user_id, timezone.now().date())

    @patch("apps.monitoring.tasks.RedisClient")
    def test_aggregate_user_metrics_default_date(self, mock_redis):
        """Test aggregation with default date (today)."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        result = aggregate_user_metrics(self.user_id)  # No date specified

        self.assertIn("Aggregated metrics", result)
        mock_redis_instance.set_metrics_cache.assert_called_once()

    @patch("apps.monitoring.tasks.RedisClient")
    def test_aggregate_user_metrics_with_complex_data(self, mock_redis):
        """Test aggregation with complex metrics data."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        # Add more complex data
        CodeMetrics.objects.create(
            session=self.session, file_path="/path/to/file1.py", lines_of_code=100, complexity_score=10.5
        )
        CodeMetrics.objects.create(
            session=self.session, file_path="/path/to/file2.py", lines_of_code=150, complexity_score=8.5
        )

        # Add activities and git events
        ActivityLog.objects.create(session=self.session, activity_type="file_open", file_path="/path/to/file1.py")
        GitEvent.objects.create(session=self.session, event_type="commit", commit_hash="abc123")

        today = timezone.now().date()
        result = aggregate_user_metrics(self.user_id, today)

        # Verify cached data
        call_args = mock_redis_instance.set_metrics_cache.call_args[0]
        cached_data = call_args[1]

        self.assertEqual(cached_data["total_lines_of_code"], 250)  # 100 + 150
        self.assertEqual(cached_data["code_metrics_count"], 2)
        self.assertEqual(cached_data["activities_count"], 1)
        self.assertEqual(cached_data["git_events_count"], 1)
        # Average complexity: (10.5 + 8.5) / 2 = 9.5
        self.assertEqual(float(cached_data["avg_complexity_score"]), 9.5)

    @patch("apps.monitoring.tasks.RedisClient")
    def test_aggregate_user_metrics_zero_values(self, mock_redis):
        """Test aggregation handles zero/null values correctly."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        # Use a completely different user_id to ensure isolation
        test_user_id = 777777
        today = timezone.now().date()
        start_of_day = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))
        end_of_day = start_of_day + timedelta(days=1)

        # COMPLETELY clear any existing sessions for this test user on this date
        DeveloperSession.objects.filter(
            user_id=test_user_id, session_start__gte=start_of_day, session_start__lt=end_of_day
        ).delete()

        # Verify no sessions exist before test
        existing_count = DeveloperSession.objects.filter(
            user_id=test_user_id, session_start__gte=start_of_day, session_start__lt=end_of_day
        ).count()
        self.assertEqual(existing_count, 0, f"Expected 0 existing sessions but found {existing_count}")

        # Create a fresh session with null duration for this test
        # Note: The model auto-calculates duration when session_end is provided,
        # so we need to set it to None after creation
        null_session = DeveloperSession.objects.create(
            user_id=test_user_id,
            ide_name="TestIDE",
            session_start=start_of_day + timedelta(hours=1),
            session_end=start_of_day + timedelta(hours=2),
        )

        # Override the auto-calculated duration to None for this test
        DeveloperSession.objects.filter(pk=null_session.pk).update(session_duration_minutes=None)

        # Verify the session was updated with null duration
        null_session.refresh_from_db()
        self.assertIsNone(null_session.session_duration_minutes, "Session duration should be None")

        # Verify only one session exists for this user/date
        final_count = DeveloperSession.objects.filter(
            user_id=test_user_id, session_start__gte=start_of_day, session_start__lt=end_of_day
        ).count()
        self.assertEqual(final_count, 1, f"Expected 1 session but found {final_count}")

        result = aggregate_user_metrics(test_user_id, today)

        call_args = mock_redis_instance.set_metrics_cache.call_args[0]
        cached_data = call_args[1]

        # Debug information if test fails
        if cached_data["total_duration_minutes"] != 0:
            sessions_debug = DeveloperSession.objects.filter(
                user_id=test_user_id, session_start__gte=start_of_day, session_start__lt=end_of_day
            )
            session_details = [(s.session_id, s.session_duration_minutes) for s in sessions_debug]
            self.fail(
                f"Expected 0 total_duration_minutes but got {cached_data['total_duration_minutes']}. "
                f"Sessions found: {session_details}"
            )

        # Should handle null values gracefully - Sum() returns None for null values which becomes 0
        # Django's `or 0` in the tasks.py ensures it's always 0
        self.assertEqual(cached_data["total_duration_minutes"], 0)
        self.assertEqual(cached_data["avg_complexity_score"], 0)  # No metrics with complexity
        self.assertEqual(cached_data["sessions_count"], 1)  # Should have exactly one session

    @patch("apps.monitoring.tasks.RedisClient")
    def test_aggregate_user_metrics_cache_timeout(self, mock_redis):
        """Test that cache timeout is set correctly."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        today = timezone.now().date()
        aggregate_user_metrics(self.user_id, today)

        # Verify cache timeout is 24 hours (86400 seconds)
        call_args = mock_redis_instance.set_metrics_cache.call_args
        self.assertEqual(call_args[1]["timeout"], 86400)
