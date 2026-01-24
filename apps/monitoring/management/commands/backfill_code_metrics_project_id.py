"""
Django management command to backfill project_id for existing CodeMetrics records.

This command attempts to populate the project_id field for CodeMetrics records
that don't have it set by looking at:
1. Session metadata (if project_id was stored there)
2. Matching session.project_path with projects in management service
3. Manual mapping based on repository URLs

Usage:
    python manage.py backfill_code_metrics_project_id [--dry-run] [--batch-size 1000]
"""

import logging
import re
import uuid
from typing import Optional

import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from apps.monitoring.models import CodeMetrics, DeveloperSession

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Backfill project_id for existing CodeMetrics records"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Run without making any changes to the database",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Number of records to process in each batch (default: 1000)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limit the total number of records to process",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        batch_size = options["batch_size"]
        limit = options["limit"]

        if dry_run:
            self.stdout.write(self.style.WARNING("🔍 DRY RUN MODE - No changes will be made"))

        # Get all CodeMetrics without project_id
        metrics_without_project = CodeMetrics.objects.filter(project_id__isnull=True)
        total_count = metrics_without_project.count()

        if limit:
            metrics_without_project = metrics_without_project[:limit]
            self.stdout.write(f"📊 Processing {limit} of {total_count} records without project_id")
        else:
            self.stdout.write(f"📊 Found {total_count} CodeMetrics records without project_id")

        if total_count == 0:
            self.stdout.write(self.style.SUCCESS("✅ All CodeMetrics records already have project_id!"))
            return

        updated_count = 0
        skipped_count = 0
        error_count = 0

        # Process in batches
        for i in range(0, total_count if not limit else limit, batch_size):
            batch = metrics_without_project[i : i + batch_size]
            self.stdout.write(f"\n🔄 Processing batch {i // batch_size + 1} ({i + 1} to {min(i + batch_size, total_count)})...")

            for metric in batch:
                try:
                    project_id = self._determine_project_id(metric)

                    if project_id:
                        if not dry_run:
                            metric.project_id = project_id
                            metric.save(update_fields=["project_id"])
                        updated_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  ✓ Updated metric {metric.metrics_id} with project_id {project_id}"
                            )
                        )
                    else:
                        skipped_count += 1
                        self.stdout.write(
                            self.style.WARNING(f"  ⚠ Could not determine project_id for metric {metric.metrics_id}")
                        )

                except Exception as e:
                    error_count += 1
                    logger.error(f"Error processing metric {metric.metrics_id}: {str(e)}")
                    self.stdout.write(self.style.ERROR(f"  ✗ Error processing metric {metric.metrics_id}: {str(e)}"))

        # Summary
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS(f"✅ Backfill complete!"))
        self.stdout.write(f"📈 Total processed: {total_count}")
        self.stdout.write(self.style.SUCCESS(f"✓ Updated: {updated_count}"))
        self.stdout.write(self.style.WARNING(f"⚠ Skipped: {skipped_count}"))
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f"✗ Errors: {error_count}"))

        if dry_run:
            self.stdout.write(self.style.WARNING("\n🔍 DRY RUN - No changes were actually made"))

    def _determine_project_id(self, metric: CodeMetrics) -> Optional[uuid.UUID]:
        """
        Attempt to determine the project_id for a CodeMetrics record.

        Strategy:
        1. Check session metadata for project_id
        2. Extract from session.project_path if it contains a UUID
        3. Query management service API to find matching project
        4. Return None if unable to determine

        Args:
            metric: CodeMetrics instance

        Returns:
            UUID of the project if found, None otherwise
        """
        session = metric.session

        # Strategy 1: Check session metadata
        if session.session_metadata and "project_id" in session.session_metadata:
            try:
                project_id_str = session.session_metadata["project_id"]
                return uuid.UUID(project_id_str)
            except (ValueError, TypeError):
                pass

        # Strategy 2: Extract UUID from project_path
        if session.project_path:
            # Look for UUID pattern in project path
            uuid_pattern = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
            matches = re.findall(uuid_pattern, session.project_path, re.IGNORECASE)
            if matches:
                try:
                    return uuid.UUID(matches[0])
                except ValueError:
                    pass

        # Strategy 3: Query management service (if available)
        # This requires the management service to be accessible
        # Uncomment and configure if you want to use this strategy
        """
        try:
            project_id = self._query_management_service(session)
            if project_id:
                return project_id
        except Exception as e:
            logger.warning(f"Failed to query management service: {str(e)}")
        """

        return None

    def _query_management_service(self, session: DeveloperSession) -> Optional[uuid.UUID]:
        """
        Query the management service to find a matching project.

        This is an optional strategy that requires the management service to be accessible.

        Args:
            session: DeveloperSession instance

        Returns:
            UUID of the project if found, None otherwise
        """
        management_service_url = getattr(settings, "MANAGEMENT_SERVICE_URL", None)
        if not management_service_url:
            return None

        try:
            # Example: Query projects by repository URL
            if session.git_repository_url:
                response = requests.get(
                    f"{management_service_url}/management/projects/",
                    params={"repository_url": session.git_repository_url},
                    timeout=5,
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get("results") and len(data["results"]) > 0:
                        return uuid.UUID(data["results"][0]["id"])
        except Exception as e:
            logger.warning(f"Failed to query management service: {str(e)}")

        return None
