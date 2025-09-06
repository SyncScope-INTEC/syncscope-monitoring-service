"""
Celery tasks for monitoring service background processing.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .logging_utils import monitoring_logger
from .models import ActivityLog, CodeMetrics, DeveloperSession, GitEvent
from .redis_client import RedisClient

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_session_analytics(self, session_id):
    """
    Process analytics for a completed session.
    """
    try:
        session = DeveloperSession.objects.get(session_id=session_id)

        # Calculate session statistics
        activities_count = ActivityLog.objects.filter(session=session).count()
        code_metrics_count = CodeMetrics.objects.filter(session=session).count()
        git_events_count = GitEvent.objects.filter(session=session).count()

        # Update session metadata with analytics
        analytics_data = {
            "activities_count": activities_count,
            "code_metrics_count": code_metrics_count,
            "git_events_count": git_events_count,
            "processed_at": timezone.now().isoformat(),
        }

        session.session_metadata.update({"analytics": analytics_data})
        session.save()

        monitoring_logger.log_performance(
            "session_analytics_processing",
            duration=0,  # Could measure actual processing time
            session_id=str(session_id),
            activities_count=activities_count,
        )

        return f"Processed analytics for session {session_id}"

    except DeveloperSession.DoesNotExist:
        logger.error(f"Session {session_id} not found for analytics processing")
        return f"Session {session_id} not found"

    except Exception as e:
        logger.error(f"Error processing analytics for session {session_id}: {e}")
        self.retry(countdown=60 * (self.request.retries + 1))


@shared_task
def cleanup_expired_sessions():
    """
    Clean up sessions that have been inactive for too long.
    """
    try:
        # Find sessions that started more than 24 hours ago and are still active
        cutoff_time = timezone.now() - timedelta(hours=24)
        expired_sessions = DeveloperSession.objects.filter(session_start__lt=cutoff_time, session_end__isnull=True)

        redis_client = RedisClient()
        count = 0

        for session in expired_sessions:
            # End the session
            session.session_end = timezone.now()
            session.save()

            # Remove from Redis cache
            redis_client.delete_session_data(str(session.session_id))

            monitoring_logger.log_session_event("auto_expired", session.session_id, session.user_id, reason="24_hour_timeout")

            count += 1

        logger.info(f"Cleaned up {count} expired sessions")
        return f"Cleaned up {count} expired sessions"

    except Exception as e:
        logger.error(f"Error cleaning up expired sessions: {e}")
        raise


@shared_task(bind=True, max_retries=3)
def aggregate_user_metrics(self, user_id, date=None):
    """
    Aggregate metrics for a user for a specific date.
    """
    try:
        from django.db.models import Avg, Count, Sum

        target_date = timezone.now().date() if date is None else date
        start_datetime = timezone.make_aware(timezone.datetime.combine(target_date, timezone.datetime.min.time()))
        end_datetime = start_datetime + timedelta(days=1)

        # Get sessions for the date
        sessions = DeveloperSession.objects.filter(
            user_id=user_id, session_start__gte=start_datetime, session_start__lt=end_datetime
        )

        if not sessions.exists():
            return f"No sessions found for user {user_id} on {target_date}"

        # Aggregate metrics
        aggregated_data = {
            "date": target_date.isoformat(),
            "user_id": user_id,
            "sessions_count": sessions.count(),
            "total_duration_minutes": sessions.aggregate(total=Sum("session_duration_minutes"))["total"] or 0,
            "activities_count": ActivityLog.objects.filter(session__in=sessions).count(),
            "code_metrics_count": CodeMetrics.objects.filter(session__in=sessions).count(),
            "git_events_count": GitEvent.objects.filter(session__in=sessions).count(),
            "total_lines_of_code": CodeMetrics.objects.filter(session__in=sessions).aggregate(total=Sum("lines_of_code"))[
                "total"
            ]
            or 0,
            "avg_complexity_score": CodeMetrics.objects.filter(session__in=sessions, complexity_score__isnull=False).aggregate(
                avg=Avg("complexity_score")
            )["avg"]
            or 0,
        }

        # Cache the aggregated data
        redis_client = RedisClient()
        cache_key = f"user_metrics:{user_id}:{target_date}"
        redis_client.set_metrics_cache(cache_key, aggregated_data, timeout=86400)  # 24 hours

        monitoring_logger.log_performance(
            "user_metrics_aggregation",
            duration=0,
            user_id=user_id,
            date=target_date.isoformat(),
            sessions_processed=aggregated_data["sessions_count"],
        )

        return f"Aggregated metrics for user {user_id} on {target_date}"

    except Exception as e:
        logger.error(f"Error aggregating metrics for user {user_id}: {e}")
        self.retry(countdown=300 * (self.request.retries + 1))  # 5 min, 10 min, 15 min


@shared_task
def send_analytics_to_service():
    """
    Send aggregated analytics data to the analytics service.
    """
    try:
        from datetime import date

        import requests
        from django.conf import settings

        # Get yesterday's data for all users who had sessions
        yesterday = timezone.now().date() - timedelta(days=1)
        start_datetime = timezone.make_aware(timezone.datetime.combine(yesterday, timezone.datetime.min.time()))
        end_datetime = start_datetime + timedelta(days=1)

        # Get unique users with sessions yesterday
        user_ids = (
            DeveloperSession.objects.filter(session_start__gte=start_datetime, session_start__lt=end_datetime)
            .values_list("user_id", flat=True)
            .distinct()
        )

        analytics_data = []
        for user_id in user_ids:
            # Trigger aggregation task for each user
            result = aggregate_user_metrics.delay(user_id, yesterday)
            analytics_data.append({"user_id": user_id, "date": yesterday.isoformat(), "task_id": result.id})

        # Send to analytics service (if configured)
        analytics_service_url = getattr(settings, "ANALYTICS_SERVICE_URL", None)
        if analytics_service_url:
            response = requests.post(
                f"{analytics_service_url}/analytics/monitoring-data/",
                json={"date": yesterday.isoformat(), "users_processed": len(user_ids), "data_available": True},
                timeout=30,
            )

            if response.status_code == 200:
                logger.info(f"Sent analytics data to service for {len(user_ids)} users")
            else:
                logger.warning(f"Failed to send analytics data: {response.status_code}")

        return f"Processed analytics for {len(user_ids)} users on {yesterday}"

    except Exception as e:
        logger.error(f"Error sending analytics to service: {e}")
        raise


from .db_utils import DatabaseManager


@shared_task
def health_check_task():
    """
    Background health check task for monitoring service status.
    """
    try:
        # Check database connection
        db_healthy = DatabaseManager.test_connection()

        # Check Redis connection
        redis_client = RedisClient()
        redis_healthy = True
        try:
            redis_client.redis_client.ping()
        except Exception:
            redis_healthy = False

        # Log health status
        monitoring_logger.log_performance(
            "health_check",
            duration=0,
            database_healthy=db_healthy,
            redis_healthy=redis_healthy,
            service_healthy=db_healthy and redis_healthy,
        )

        return {"database": db_healthy, "redis": redis_healthy, "overall": db_healthy and redis_healthy}

    except Exception as e:
        logger.error(f"Health check task failed: {e}")
        return {"error": str(e), "overall": False}
