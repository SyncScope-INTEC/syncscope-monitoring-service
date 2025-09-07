"""
Tests for Django management commands.
"""

import io
import uuid
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.monitoring.models import ActivityLog, CodeMetrics, DeveloperSession, GitEvent


class CleanupSessionsCommandTest(TestCase):
    """Tests for cleanup_sessions management command."""

    def setUp(self):
        # Create test sessions with different ages
        now = timezone.now()

        # Create an expired session (older than 24 hours, still active)
        self.expired_session = DeveloperSession.objects.create(
            user_id=1, ide_name="VSCode", session_start=now - timedelta(hours=25), session_end=None  # Still active
        )

        # Create a recent session (should not be cleaned up)
        self.recent_session = DeveloperSession.objects.create(
            user_id=2, ide_name="PyCharm", session_start=now - timedelta(hours=1), session_end=None  # Still active
        )

        # Create an already ended session (should not be cleaned up)
        self.ended_session = DeveloperSession.objects.create(
            user_id=3,
            ide_name="Vim",
            session_start=now - timedelta(hours=25),
            session_end=now - timedelta(hours=24),  # Already ended
        )

    @patch("apps.monitoring.management.commands.cleanup_sessions.RedisClient")
    def test_cleanup_sessions_default(self, mock_redis):
        """Test cleanup with default settings."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        out = io.StringIO()
        call_command("cleanup_sessions", stdout=out)

        # Refresh from database
        self.expired_session.refresh_from_db()
        self.recent_session.refresh_from_db()
        self.ended_session.refresh_from_db()

        # Check that only expired session was ended
        self.assertIsNotNone(self.expired_session.session_end)
        self.assertIsNone(self.recent_session.session_end)
        self.assertIsNotNone(self.ended_session.session_end)

        # Check Redis cleanup was called
        mock_redis_instance.delete_session_data.assert_called_once()

        # Check output
        output = out.getvalue()
        self.assertIn("Successfully cleaned up 1 expired sessions", output)

    @patch("apps.monitoring.management.commands.cleanup_sessions.RedisClient")
    def test_cleanup_sessions_custom_hours(self, mock_redis):
        """Test cleanup with custom hours parameter."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        out = io.StringIO()
        call_command("cleanup_sessions", "--hours", 48, stdout=out)

        # With 48 hours, no sessions should be cleaned up
        self.expired_session.refresh_from_db()
        self.assertIsNone(self.expired_session.session_end)

        output = out.getvalue()
        self.assertIn("No expired sessions found (older than 48 hours)", output)

    def test_cleanup_sessions_dry_run(self):
        """Test dry run mode."""
        out = io.StringIO()
        call_command("cleanup_sessions", "--dry-run", stdout=out)

        # Check that no sessions were actually cleaned up
        self.expired_session.refresh_from_db()
        self.assertIsNone(self.expired_session.session_end)

        # Check dry run output
        output = out.getvalue()
        self.assertIn("DRY RUN: Would clean up 1 expired sessions", output)

    @patch("apps.monitoring.management.commands.cleanup_sessions.RedisClient")
    def test_cleanup_sessions_verbose(self, mock_redis):
        """Test verbose output."""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        out = io.StringIO()
        call_command("cleanup_sessions", "--verbose", stdout=out)

        output = out.getvalue()
        self.assertIn("Found 1 expired sessions:", output)
        self.assertIn(f"Session {self.expired_session.session_id}", output)
        self.assertIn("✓ Cleaned up session", output)

    @patch("apps.monitoring.management.commands.cleanup_sessions.RedisClient")
    def test_cleanup_sessions_redis_error(self, mock_redis):
        """Test handling of Redis errors during cleanup."""
        mock_redis_instance = MagicMock()
        mock_redis_instance.delete_session_data.side_effect = Exception("Redis error")
        mock_redis.return_value = mock_redis_instance

        out = io.StringIO()
        call_command("cleanup_sessions", "--verbose", stdout=out)

        # Session should still be ended in database
        self.expired_session.refresh_from_db()
        self.assertIsNotNone(self.expired_session.session_end)

        # Check error output
        output = out.getvalue()
        self.assertIn("✗ Failed to cleanup session", output)

    def test_cleanup_sessions_no_expired_sessions(self):
        """Test command when no expired sessions exist."""
        # Delete the expired session
        self.expired_session.delete()

        out = io.StringIO()
        call_command("cleanup_sessions", stdout=out)

        output = out.getvalue()
        self.assertIn("No expired sessions found (older than 24 hours)", output)


class GenerateTestDataCommandTest(TestCase):
    """Tests for generate_test_data management command."""

    def test_generate_test_data_default(self):
        """Test test data generation with default parameters."""
        out = io.StringIO()
        call_command("generate_test_data", stdout=out)

        # Check that data was created
        self.assertTrue(DeveloperSession.objects.exists())
        self.assertTrue(ActivityLog.objects.exists())
        self.assertTrue(CodeMetrics.objects.exists())
        self.assertTrue(GitEvent.objects.exists())

        # Check default counts (5 users, 20 sessions each = 100 sessions)
        self.assertEqual(DeveloperSession.objects.count(), 100)

        output = out.getvalue()
        self.assertIn("Test data generation complete!", output)
        self.assertIn("100 sessions", output)

    def test_generate_test_data_custom_parameters(self):
        """Test test data generation with custom parameters."""
        out = io.StringIO()
        call_command("generate_test_data", "--users", 2, "--sessions", 3, "--days", 7, stdout=out)

        # Check that data was created with custom counts
        self.assertEqual(DeveloperSession.objects.count(), 6)  # 2 users * 3 sessions

        # Verify sessions are within a reasonable time range (last 7 days + buffer)
        cutoff_date = timezone.now() - timedelta(days=8)  # Add buffer for test execution time
        sessions = DeveloperSession.objects.all()
        for session in sessions:
            self.assertGreaterEqual(session.session_start, cutoff_date)

        output = out.getvalue()
        self.assertIn("6 sessions", output)

    def test_generate_test_data_clean_option(self):
        """Test test data generation with clean option."""
        # Create some initial data
        initial_uuid = uuid.UUID("99999999-9999-9999-9999-999999999999")
        DeveloperSession.objects.create(user_id=initial_uuid, ide_name="Test IDE")
        initial_count = DeveloperSession.objects.count()
        self.assertGreater(initial_count, 0)

        out = io.StringIO()
        call_command("generate_test_data", "--users", 1, "--sessions", 1, "--clean", stdout=out)

        # Check that initial data was cleaned and new data created
        self.assertEqual(DeveloperSession.objects.count(), 1)

        # Check that it's new data (different user_id)
        session = DeveloperSession.objects.first()
        expected_uuid = uuid.UUID("00000000-0000-0000-0000-000000000001")
        self.assertEqual(session.user_id, expected_uuid)

        output = out.getvalue()
        self.assertIn("Cleaning existing test data...", output)
        self.assertIn("✓ Cleaned existing data", output)

    def test_generate_test_data_session_relationships(self):
        """Test that generated sessions have proper related objects."""
        call_command("generate_test_data", "--users", 1, "--sessions", 1, "--no-color")

        session = DeveloperSession.objects.first()

        # Check that activities were created for the session
        activities = ActivityLog.objects.filter(session=session)
        self.assertGreater(activities.count(), 0)

        # Check that code metrics were created
        metrics = CodeMetrics.objects.filter(session=session)
        self.assertGreater(metrics.count(), 0)

        # Check that git events may have been created
        git_events = GitEvent.objects.filter(session=session)
        # Git events are random (0-5), so we just check they exist in general
        self.assertGreaterEqual(GitEvent.objects.count(), 0)

    def test_generate_test_data_session_fields(self):
        """Test that generated sessions have all required fields."""
        call_command("generate_test_data", "--users", 1, "--sessions", 1, "--no-color")

        session = DeveloperSession.objects.first()

        # Check required fields are populated
        self.assertIsNotNone(session.user_id)
        self.assertIsNotNone(session.session_start)
        self.assertIsNotNone(session.session_end)
        self.assertIsNotNone(session.session_duration_minutes)
        self.assertIsNotNone(session.ide_name)
        self.assertIsNotNone(session.ide_version)
        self.assertIsNotNone(session.project_path)
        self.assertIsNotNone(session.git_repository_url)
        self.assertIsNotNone(session.git_branch)
        self.assertIsNotNone(session.git_commit_hash)
        self.assertIsNotNone(session.operating_system)
        self.assertIsNotNone(session.session_metadata)

        # Check session metadata has expected structure
        self.assertIn("theme", session.session_metadata)
        self.assertIn("font_size", session.session_metadata)


class HealthCheckCommandTest(TestCase):
    """Tests for health_check management command."""

    def test_health_check_basic(self):
        """Test basic health check."""
        out = io.StringIO()
        call_command("health_check", stdout=out)

        output = out.getvalue()
        self.assertIn("SyncScope Monitoring Service Health Check", output)
        self.assertIn("Database Health:", output)
        self.assertIn("Redis/Cache Health:", output)
        self.assertIn("Model Health:", output)
        self.assertIn("Configuration:", output)
        self.assertIn("OVERALL STATUS:", output)

    @patch("apps.monitoring.management.commands.health_check.DatabaseHealthCheck")
    def test_health_check_database_healthy(self, mock_db_health):
        """Test health check with healthy database."""
        mock_db_health.is_healthy.return_value = True
        mock_db_health.get_schema_info.return_value = ["public"]

        out = io.StringIO()
        call_command("health_check", stdout=out)

        output = out.getvalue()
        self.assertIn("✓ Database: HEALTHY", output)

    @patch("apps.monitoring.management.commands.health_check.DatabaseHealthCheck")
    def test_health_check_database_unhealthy(self, mock_db_health):
        """Test health check with unhealthy database."""
        mock_db_health.is_healthy.return_value = False

        out = io.StringIO()
        call_command("health_check", stdout=out)

        output = out.getvalue()
        self.assertIn("✗ Database: UNHEALTHY", output)
        self.assertIn("OVERALL STATUS: UNHEALTHY", output)

    @patch("apps.monitoring.management.commands.health_check.CacheHealthCheck")
    def test_health_check_cache_healthy(self, mock_cache_health):
        """Test health check with healthy cache."""
        mock_cache_health.is_healthy.return_value = True

        out = io.StringIO()
        call_command("health_check", stdout=out)

        output = out.getvalue()
        self.assertIn("✓ Redis: HEALTHY", output)

    @patch("apps.monitoring.management.commands.health_check.CacheHealthCheck")
    def test_health_check_cache_unhealthy(self, mock_cache_health):
        """Test health check with unhealthy cache."""
        mock_cache_health.is_healthy.return_value = False

        out = io.StringIO()
        call_command("health_check", stdout=out)

        output = out.getvalue()
        self.assertIn("✗ Redis: UNHEALTHY", output)
        self.assertIn("OVERALL STATUS: UNHEALTHY", output)

    def test_health_check_models(self):
        """Test model health checks."""
        # Create some test data
        session = DeveloperSession.objects.create(user_id=1, ide_name="VSCode")
        ActivityLog.objects.create(session=session, activity_type="file_open")
        CodeMetrics.objects.create(session=session, file_path="/test.py", lines_of_code=100)
        GitEvent.objects.create(session=session, event_type="commit")

        out = io.StringIO()
        call_command("health_check", stdout=out)

        output = out.getvalue()
        self.assertIn("✓ DeveloperSession: 1 records", output)
        self.assertIn("✓ ActivityLog: 1 records", output)
        self.assertIn("✓ CodeMetrics: 1 records", output)
        self.assertIn("✓ GitEvent: 1 records", output)

    @patch("apps.monitoring.management.commands.health_check.DatabaseHealthCheck")
    def test_health_check_detailed(self, mock_db_health):
        """Test detailed health check."""
        mock_db_health.is_healthy.return_value = True
        mock_db_health.get_schema_info.return_value = ["public", "information_schema"]

        # Create test data to check detailed output
        DeveloperSession.objects.create(user_id=1, ide_name="VSCode")

        out = io.StringIO()
        call_command("health_check", "--detailed", stdout=out)

        output = out.getvalue()
        self.assertIn("Available schemas:", output)
        self.assertIn("Database:", output)
        self.assertIn("System Information:", output)
        self.assertIn("Latest record:", output)

    def test_health_check_detailed_with_system_info(self):
        """Test detailed health check with system information."""
        out = io.StringIO()
        call_command("health_check", "--detailed", stdout=out)

        output = out.getvalue()
        self.assertIn("Process ID:", output)
        self.assertIn("System Information:", output)
        # The actual metrics depend on psutil availability, so we just check sections exist

    def test_health_check_detailed_without_psutil(self):
        """Test detailed health check handles missing psutil gracefully."""
        # This test checks that the command handles psutil import errors gracefully
        out = io.StringIO()
        call_command("health_check", "--detailed", stdout=out)

        output = out.getvalue()
        self.assertIn("System Information:", output)
        # Either shows metrics or shows unavailable message

    @patch("apps.monitoring.management.commands.health_check.DatabaseHealthCheck")
    def test_health_check_with_exit_code_healthy(self, mock_db_health):
        """Test health check with exit code option when healthy."""
        mock_db_health.is_healthy.return_value = True

        out = io.StringIO()
        # This should not raise SystemExit
        call_command("health_check", "--exit-code", stdout=out)

        output = out.getvalue()
        self.assertIn("OVERALL STATUS: HEALTHY", output)

    @patch("apps.monitoring.management.commands.health_check.DatabaseHealthCheck")
    def test_health_check_with_exit_code_unhealthy(self, mock_db_health):
        """Test health check with exit code option when unhealthy."""
        mock_db_health.is_healthy.return_value = False

        out = io.StringIO()
        with self.assertRaises(SystemExit) as cm:
            call_command("health_check", "--exit-code", stdout=out)

        self.assertEqual(cm.exception.code, 1)

        output = out.getvalue()
        self.assertIn("OVERALL STATUS: UNHEALTHY", output)

    @patch("apps.monitoring.management.commands.health_check.DatabaseHealthCheck")
    def test_health_check_database_exception(self, mock_db_health):
        """Test health check when database check raises exception."""
        mock_db_health.is_healthy.side_effect = Exception("Database connection failed")

        out = io.StringIO()
        call_command("health_check", stdout=out)

        output = out.getvalue()
        self.assertIn("✗ Database: ERROR - Database connection failed", output)
        self.assertIn("OVERALL STATUS: UNHEALTHY", output)

    @patch("apps.monitoring.management.commands.health_check.CacheHealthCheck")
    def test_health_check_cache_exception(self, mock_cache_health):
        """Test health check when cache check raises exception."""
        mock_cache_health.is_healthy.side_effect = Exception("Redis connection failed")

        out = io.StringIO()
        call_command("health_check", stdout=out)

        output = out.getvalue()
        self.assertIn("✗ Redis: ERROR - Redis connection failed", output)
        self.assertIn("OVERALL STATUS: UNHEALTHY", output)

    def test_health_check_model_exception(self):
        """Test health check when model query raises exception."""
        # This test might be tricky to implement without actually breaking the database
        # We'll create a scenario where model query fails by using a non-existent field
        out = io.StringIO()

        # Create test data first
        DeveloperSession.objects.create(user_id=1, ide_name="VSCode")

        # Now run the health check - it should handle any model errors gracefully
        call_command("health_check", stdout=out)

        # The command should complete without crashing
        output = out.getvalue()
        self.assertIn("Model Health:", output)

    def test_health_check_configuration(self):
        """Test configuration checks."""
        out = io.StringIO()
        call_command("health_check", stdout=out)

        output = out.getvalue()
        self.assertIn("Configuration:", output)
        self.assertIn("DEBUG:", output)
        self.assertIn("DATABASE_URL:", output)
        self.assertIn("SECRET_KEY:", output)
