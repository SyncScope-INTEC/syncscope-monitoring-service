"""
Management command to cleanup expired sessions.
"""

import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.monitoring.models import DeveloperSession
from apps.monitoring.redis_client import RedisClient
from config.database_retry import database_retry

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Cleanup expired developer sessions"

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours", type=int, default=24, help="Sessions older than this many hours will be expired (default: 24)"
        )
        parser.add_argument("--dry-run", action="store_true", help="Show what would be cleaned up without making changes")
        parser.add_argument("--verbose", action="store_true", help="Verbose output")

    @database_retry(max_retries=3)
    def handle(self, *args, **options):
        hours = options["hours"]
        dry_run = options["dry_run"]
        verbose = options["verbose"]

        cutoff_time = timezone.now() - timezone.timedelta(hours=hours)

        # Find expired sessions
        expired_sessions = DeveloperSession.objects.filter(session_start__lt=cutoff_time, session_end__isnull=True)

        count = expired_sessions.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS(f"No expired sessions found (older than {hours} hours)"))
            return

        if verbose:
            self.stdout.write(f"Found {count} expired sessions:")
            for session in expired_sessions:
                age = timezone.now() - session.session_start
                self.stdout.write(
                    f"  - Session {session.session_id} (user {session.user_id}) "
                    f"age: {age.days} days, {age.seconds // 3600} hours"
                )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"DRY RUN: Would clean up {count} expired sessions " f"(older than {hours} hours)")
            )
            return

        # Cleanup expired sessions
        redis_client = RedisClient()
        cleaned_count = 0

        for session in expired_sessions:
            try:
                # End the session
                session.session_end = timezone.now()
                session.save()

                # Remove from Redis cache
                redis_client.delete_session_data(str(session.session_id))

                cleaned_count += 1

                if verbose:
                    self.stdout.write(f"  ✓ Cleaned up session {session.session_id}")

            except Exception as e:
                logger.error(f"Failed to cleanup session {session.session_id}: {e}")
                self.stdout.write(self.style.ERROR(f"  ✗ Failed to cleanup session {session.session_id}: {e}"))

        if cleaned_count > 0:
            self.stdout.write(self.style.SUCCESS(f"Successfully cleaned up {cleaned_count} expired sessions"))
        else:
            self.stdout.write(self.style.ERROR("Failed to clean up any sessions"))
