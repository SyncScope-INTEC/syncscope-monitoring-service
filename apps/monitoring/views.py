import logging

from django.db import models
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template import loader
from django.utils import timezone
from drf_spectacular.openapi import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from config.database_retry import DatabaseHealthCheck

from .auth_utils import get_user_from_request
from .db_mixins import ServerlessViewMixin
from .decorators import activity_ratelimit, git_events_ratelimit, health_ratelimit, metrics_ratelimit, session_ratelimit
from .logging_utils import monitoring_logger
from .mixins import CacheHealthCheck, PerformanceMonitoringMixin
from .models import ActivityLog, CodeMetrics, DeveloperSession, GitEvent
from .permissions import CanAccessUserData, IsAuthenticated
from .redis_client import RedisClient
from .serializers import (
    ActivityLogSerializer,
    BulkActivitySerializer,
    CodeMetricsSerializer,
    DeveloperSessionSerializer,
    GitEventSerializer,
    SessionEndSerializer,
    SessionStartSerializer,
)
from .tasks import process_session_analytics

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([AllowAny])
def api_home(request):
    """
    API Home page showing main navigation routes and service links.
    """
    # Define the main navigation routes
    main_routes = [
        {
            "title": "API Documentation",
            "description": "Interactive API documentation with live testing",
            "url": request.build_absolute_uri("/api/docs/"),
            "icon": "📖",
            "category": "documentation",
        },
        {
            "title": "ReDoc Documentation",
            "description": "Clean, three-panel OpenAPI documentation",
            "url": request.build_absolute_uri("/api/redoc/"),
            "icon": "📚",
            "category": "documentation",
        },
        {
            "title": "OpenAPI Schema",
            "description": "Raw OpenAPI specification in JSON format",
            "url": request.build_absolute_uri("/api/schema/"),
            "icon": "⚙️",
            "category": "documentation",
        },
        {
            "title": "Admin Interface",
            "description": "Django admin panel for monitoring data management",
            "url": request.build_absolute_uri("/admin/"),
            "icon": "🔧",
            "category": "admin",
        },
        {
            "title": "Health Check",
            "description": "Service health status and monitoring",
            "url": request.build_absolute_uri("/health/"),
            "icon": "❤️",
            "category": "monitoring",
        },
    ]

    # Quick stats about the service
    service_info = {
        "endpoints": 12,
        "auth_methods": ["JWT", "Service Token"],
        "features": ["Session Tracking", "Activity Monitoring", "Code Metrics", "Git Events"],
        "status": "Operational",
    }

    context = {
        "main_routes": main_routes,
        "service_info": service_info,
        "api_title": "SyncScope Monitoring Service",
        "api_version": "1.0.0",
        "api_description": "Developer activity monitoring and metrics collection service",
        "base_url": request.build_absolute_uri("/"),
    }

    # Check if JSON format is explicitly requested
    if request.GET.get("format") == "json":
        return Response(context, status=status.HTTP_200_OK)

    # Try to render HTML template first, fallback to JSON
    try:
        template = loader.get_template("monitoring/api_home.html")
        return HttpResponse(template.render(context, request))
    except Exception as e:
        # Log the error for debugging
        logger.error(f"Template loading error: {str(e)}")
        # Fallback to JSON response if template doesn't exist
        return Response(context, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Health"],
    responses={
        200: {
            "description": "Service health status",
            "example": {
                "status": "healthy",
                "service": "syncscope-monitoring-service",
                "version": "1.0.0",
                "timestamp": "2024-01-01T00:00:00Z",
                "checks": {"database": "healthy", "redis": "healthy"},
            },
        },
        503: {"description": "Service unhealthy"},
    },
)
@api_view(["GET"])
@permission_classes([AllowAny])
@health_ratelimit
def health_check(request):
    """Comprehensive health check endpoint."""
    import time

    from django.conf import settings

    start_time = time.time()
    checks = {}
    overall_healthy = True

    # Check database
    try:
        db_healthy = DatabaseHealthCheck.is_healthy(use_cache=False)
        checks["database"] = "healthy" if db_healthy else "unhealthy"
        if not db_healthy:
            overall_healthy = False
    except Exception as e:
        checks["database"] = f"error: {str(e)}"
        overall_healthy = False

    # Check Redis/Cache
    try:
        cache_healthy = CacheHealthCheck.is_healthy()
        checks["redis"] = "healthy" if cache_healthy else "unhealthy"
        if not cache_healthy:
            overall_healthy = False
    except Exception as e:
        checks["redis"] = f"error: {str(e)}"
        overall_healthy = False

    # Get schema info
    try:
        schemas = DatabaseHealthCheck.get_schema_info()
        checks["schemas"] = schemas if schemas else ["public"]
    except Exception:
        checks["schemas"] = ["unknown"]

    response_time = round((time.time() - start_time) * 1000, 2)

    response_data = {
        "status": "healthy" if overall_healthy else "unhealthy",
        "service": "syncscope-monitoring-service",
        "version": getattr(settings, "VERSION", "1.0.0"),
        "timestamp": timezone.now().isoformat(),
        "response_time_ms": response_time,
        "checks": checks,
    }

    status_code = status.HTTP_200_OK if overall_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return Response(response_data, status=status_code)


@extend_schema(tags=["Health"], responses={200: {"description": "Liveness probe - service is running"}})
@api_view(["GET"])
@permission_classes([AllowAny])
def liveness_check(request):
    """Liveness probe endpoint for Kubernetes."""
    return Response(
        {"status": "alive", "service": "syncscope-monitoring-service", "timestamp": timezone.now().isoformat()},
        status=status.HTTP_200_OK,
    )


@extend_schema(
    tags=["Health"],
    responses={
        200: {"description": "Readiness probe - service is ready to accept traffic"},
        503: {"description": "Service not ready"},
    },
)
@api_view(["GET"])
@permission_classes([AllowAny])
def readiness_check(request):
    """Readiness probe endpoint for Kubernetes."""
    # Check critical dependencies
    db_ready = DatabaseHealthCheck.is_healthy()
    cache_ready = CacheHealthCheck.is_healthy()

    ready = db_ready and cache_ready

    response_data = {
        "status": "ready" if ready else "not_ready",
        "service": "syncscope-monitoring-service",
        "timestamp": timezone.now().isoformat(),
        "dependencies": {"database": "ready" if db_ready else "not_ready", "redis": "ready" if cache_ready else "not_ready"},
    }

    status_code = status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return Response(response_data, status=status_code)


@extend_schema(
    tags=["Sessions"],
    request=SessionStartSerializer,
    responses={201: DeveloperSessionSerializer},
    description="Start a new developer monitoring session",
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@session_ratelimit
def start_session(request):
    """Start a new developer monitoring session."""
    try:
        serializer = SessionStartSerializer(data=request.data)
        if serializer.is_valid():
            # Create new session
            session = serializer.save()

            # Cache session data in Redis
            redis_client = RedisClient()
            session_data = {
                "session_id": str(session.session_id),
                "user_id": session.user_id,
                "started_at": session.session_start.isoformat(),
            }
            redis_client.set_session_data(str(session.session_id), session_data)

            response_serializer = DeveloperSessionSerializer(session)
            monitoring_logger.log_session_event(
                "started", session.session_id, session.user_id, ide_name=session.ide_name, project_path=session.project_path
            )

            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error(f"Error starting session: {e}")
        return Response({"error": "Failed to start session"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=["Sessions"],
    request=SessionEndSerializer,
    responses={200: DeveloperSessionSerializer},
    description="End an existing developer monitoring session",
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@session_ratelimit
def end_session(request):
    """End an existing developer monitoring session."""
    try:
        serializer = SessionEndSerializer(data=request.data)
        if serializer.is_valid():
            session_id = serializer.validated_data["session_id"]
            session_metadata = serializer.validated_data.get("session_metadata", {})

            # Get the session
            session = get_object_or_404(DeveloperSession, session_id=session_id)

            # End the session
            if not session.session_end:
                session.session_end = timezone.now()
                if session_metadata:
                    session.session_metadata.update(session_metadata)
                session.save()

                # Remove from Redis cache
                redis_client = RedisClient()
                redis_client.delete_session_data(str(session_id))

                monitoring_logger.log_session_event(
                    "ended", session_id, session.user_id, duration_minutes=session.session_duration_minutes
                )

                # Trigger analytics processing in background
                process_session_analytics.delay(str(session_id))

            response_serializer = DeveloperSessionSerializer(session)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error(f"Error ending session: {e}")
        return Response({"error": "Failed to end session"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=["Activities"],
    request=BulkActivitySerializer,
    responses={201: {"description": "Activities created successfully"}},
    description="Bulk upload developer activities for a session",
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@activity_ratelimit
def bulk_activities(request):
    """Bulk upload developer activities for a session."""
    serializer = BulkActivitySerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    session_id = serializer.validated_data["session_id"]
    activities_data = serializer.validated_data["activities"]

    # Verify session exists (this will raise Http404 if not found)
    session = get_object_or_404(DeveloperSession, session_id=session_id)

    try:
        # Create activities in bulk
        activities = []
        for activity_data in activities_data:
            # Remove session from data as we'll set it explicitly
            activity_data.pop("session", None)
            activity = ActivityLog(session=session, **activity_data)
            activities.append(activity)

        # Bulk create for better performance
        created_activities = ActivityLog.objects.bulk_create(activities)

        monitoring_logger.log_activity_event("bulk_upload", session_id, count=len(created_activities))

        return Response(
            {
                "message": f"Successfully created {len(created_activities)} activities",
                "session_id": str(session_id),
                "activities_count": len(created_activities),
            },
            status=status.HTTP_201_CREATED,
        )

    except Exception as e:
        logger.error(f"Error creating bulk activities: {e}")
        return Response({"error": "Failed to create activities"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=["Sessions"],
    parameters=[
        OpenApiParameter(
            name="user_id",
            description="User ID to get sessions for",
            required=True,
            type=OpenApiTypes.UUID,
            location=OpenApiParameter.PATH,
        ),
        OpenApiParameter(
            name="limit",
            description="Number of sessions to return (default: 20, max: 100)",
            required=False,
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="offset",
            description="Number of sessions to skip",
            required=False,
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
        ),
        OpenApiParameter(
            name="active_only",
            description="Return only active sessions",
            required=False,
            type=OpenApiTypes.BOOL,
            location=OpenApiParameter.QUERY,
        ),
    ],
    responses={200: DeveloperSessionSerializer(many=True)},
    description="Get developer sessions for a specific user",
)
@api_view(["GET"])
@permission_classes([CanAccessUserData])
@session_ratelimit
def get_user_sessions(request, user_id):
    """Get developer sessions for a specific user."""
    try:
        # Parse query parameters
        limit = min(int(request.GET.get("limit", 20)), 100)  # Max 100
        offset = int(request.GET.get("offset", 0))
        active_only = request.GET.get("active_only", "false").lower() == "true"

        # Build queryset
        queryset = DeveloperSession.objects.filter(user_id=user_id)

        if active_only:
            queryset = queryset.filter(session_end__isnull=True)

        # Apply pagination
        total_count = queryset.count()
        sessions = queryset[offset : offset + limit]

        # Check Redis for active session data
        redis_client = RedisClient()
        serializer_data = []

        for session in sessions:
            session_data = DeveloperSessionSerializer(session).data

            # Add Redis cache data for active sessions
            if session.is_active:
                cached_data = redis_client.get_session_data(str(session.session_id))
                if cached_data:
                    session_data["cached_data"] = cached_data

            serializer_data.append(session_data)

        response_data = {"count": total_count, "next": None, "previous": None, "results": serializer_data}

        # Add pagination links
        if offset + limit < total_count:
            response_data["next"] = f"?limit={limit}&offset={offset + limit}"
        if offset > 0:
            response_data["previous"] = f"?limit={limit}&offset={max(0, offset - limit)}"

        logger.info(f"Retrieved {len(sessions)} sessions for user {user_id}")

        return Response(response_data, status=status.HTTP_200_OK)

    except ValueError as e:
        return Response({"error": "Invalid parameter format"}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Error retrieving user sessions: {e}")
        return Response({"error": "Failed to retrieve sessions"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=["Metrics"],
    request=CodeMetricsSerializer,
    responses={201: CodeMetricsSerializer},
    description="Submit code metrics for a file in a session",
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@metrics_ratelimit
def submit_code_metrics(request):
    """Submit code metrics for a file in a session."""
    try:
        serializer = CodeMetricsSerializer(data=request.data)
        if serializer.is_valid():
            # Verify session exists
            session_id = serializer.validated_data["session"].session_id
            session = get_object_or_404(DeveloperSession, session_id=session_id)

            # Check if metrics already exist for this file in this session
            existing_metrics = CodeMetrics.objects.filter(
                session=session, file_path=serializer.validated_data["file_path"]
            ).first()

            if existing_metrics:
                # Update existing metrics
                for field, value in serializer.validated_data.items():
                    if field != "session":  # Don't update the session
                        setattr(existing_metrics, field, value)
                existing_metrics.calculated_at = timezone.now()
                existing_metrics.save()

                response_serializer = CodeMetricsSerializer(existing_metrics)
                logger.info(f"Updated code metrics for {serializer.validated_data['file_path']} in session {session_id}")

                return Response(response_serializer.data, status=status.HTTP_200_OK)
            else:
                # Create new metrics
                metrics = serializer.save()

                # Cache metrics for performance analytics
                redis_client = RedisClient()
                metrics_data = {
                    "file_path": metrics.file_path,
                    "lines_of_code": metrics.lines_of_code,
                    "total_changes": metrics.total_changes,
                    "calculated_at": metrics.calculated_at.isoformat(),
                }
                redis_client.set_metrics_cache(session.user_id, metrics_data)

                response_serializer = CodeMetricsSerializer(metrics)
                logger.info(f"Created code metrics for {metrics.file_path} in session {session_id}")

                return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error(f"Error submitting code metrics: {e}")
        return Response({"error": "Failed to submit code metrics"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=["Events"],
    request=GitEventSerializer,
    responses={201: GitEventSerializer},
    description="Record a git event for a session",
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@git_events_ratelimit
def record_git_event(request):
    """Record a git event for a session."""
    try:
        serializer = GitEventSerializer(data=request.data)
        if serializer.is_valid():
            # Verify session exists
            session_id = serializer.validated_data["session"].session_id
            session = get_object_or_404(DeveloperSession, session_id=session_id)

            # Create git event
            git_event = serializer.save()

            # Update session git information if provided
            if git_event.commit_hash and not session.git_commit_hash:
                session.git_commit_hash = git_event.commit_hash
            if git_event.branch_name and not session.git_branch:
                session.git_branch = git_event.branch_name

            # Update git repository URL in session if not set
            if not session.git_repository_url and git_event.git_metadata:
                repo_url = git_event.git_metadata.get("repository_url")
                if repo_url:
                    session.git_repository_url = repo_url

            session.save()

            # Log activity for git event
            ActivityLog.objects.create(
                session=session,
                activity_type=f"git_{git_event.event_type}",
                timestamp=git_event.timestamp,
                activity_metadata={
                    "git_event_id": str(git_event.event_id),
                    "commit_hash": git_event.commit_hash,
                    "branch_name": git_event.branch_name,
                },
            )

            response_serializer = GitEventSerializer(git_event)
            logger.info(f"Recorded git event {git_event.event_type} for session {session_id}")

            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error(f"Error recording git event: {e}")
        return Response({"error": "Failed to record git event"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Additional API endpoints for Analytics Service integration


@extend_schema(
    tags=["API - Sessions"],
    parameters=[
        OpenApiParameter("user_id", OpenApiTypes.STR, description="User ID to filter sessions"),
        OpenApiParameter("start_date", OpenApiTypes.DATETIME, description="Start date for filtering"),
        OpenApiParameter("end_date", OpenApiTypes.DATETIME, description="End date for filtering"),
    ],
    responses={200: {"description": "List of user sessions"}},
    description="Get user sessions for analytics - API endpoint",
)
@api_view(["GET"])
@permission_classes([AllowAny])  # For service-to-service communication
def api_get_sessions(request):
    """Get user sessions for analytics service integration."""
    try:
        user_id = request.GET.get("user_id")
        start_date = request.GET.get("start_date")
        end_date = request.GET.get("end_date")

        queryset = DeveloperSession.objects.all()

        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if start_date:
            from dateutil.parser import parse

            start_date_parsed = parse(start_date)
            queryset = queryset.filter(session_start__gte=start_date_parsed)
        if end_date:
            from dateutil.parser import parse

            end_date_parsed = parse(end_date)
            queryset = queryset.filter(session_start__lte=end_date_parsed)

        sessions = queryset.order_by("-session_start")[:100]  # Limit to 100 recent sessions
        serializer = DeveloperSessionSerializer(sessions, many=True)

        return Response({"sessions": serializer.data, "count": len(serializer.data)}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error getting sessions for analytics: {e}")
        return Response({"error": "Failed to get sessions"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=["API - Code Metrics"],
    parameters=[
        OpenApiParameter("user_id", OpenApiTypes.STR, description="User ID to filter metrics"),
        OpenApiParameter("project_id", OpenApiTypes.STR, description="Project ID to filter metrics"),
        OpenApiParameter("start_date", OpenApiTypes.DATETIME, description="Start date for filtering"),
        OpenApiParameter("end_date", OpenApiTypes.DATETIME, description="End date for filtering"),
    ],
    responses={200: {"description": "List of code metrics"}},
    description="Get code metrics for analytics - API endpoint",
)
@api_view(["GET"])
@permission_classes([AllowAny])  # For service-to-service communication
def api_get_code_metrics(request):
    """Get code metrics for analytics service integration."""
    try:
        user_id = request.GET.get("user_id")
        project_id = request.GET.get("project_id")
        start_date = request.GET.get("start_date")
        end_date = request.GET.get("end_date")

        queryset = CodeMetrics.objects.all()

        if user_id:
            # Filter by sessions that belong to the user
            queryset = queryset.filter(session__user_id=user_id)
        if project_id:
            # Filter by project path or metadata
            queryset = queryset.filter(session__project_path__icontains=project_id)
        if start_date:
            from dateutil.parser import parse

            start_date_parsed = parse(start_date)
            queryset = queryset.filter(calculated_at__gte=start_date_parsed)
        if end_date:
            from dateutil.parser import parse

            end_date_parsed = parse(end_date)
            queryset = queryset.filter(calculated_at__lte=end_date_parsed)

        metrics = queryset.order_by("-calculated_at")[:100]  # Limit to 100 recent metrics
        serializer = CodeMetricsSerializer(metrics, many=True)

        return Response({"results": serializer.data, "count": len(serializer.data)}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error getting code metrics for analytics: {e}")
        return Response({"error": "Failed to get code metrics"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Analytics integration endpoints with proper Swagger tags
@extend_schema(
    tags=["Sessions"],
    summary="Get all user sessions for analytics",
    description="Get user sessions for analytics - API endpoint",
    parameters=[
        OpenApiParameter(name="user_id", description="User ID to filter sessions", type=OpenApiTypes.STR),
        OpenApiParameter(name="start_date", description="Start date for filtering", type=OpenApiTypes.DATETIME),
        OpenApiParameter(name="end_date", description="End date for filtering", type=OpenApiTypes.DATETIME),
    ],
    responses={
        200: {
            "description": "List of user sessions",
            "content": {"application/json": {"schema": {"description": "List of user sessions"}}},
        }
    },
)
@api_view(["GET"])
@permission_classes([AllowAny])
def get_all_sessions(request):
    """Get user sessions for analytics - API endpoint"""
    try:
        user_id = request.GET.get("user_id")
        start_date = request.GET.get("start_date")
        end_date = request.GET.get("end_date")

        queryset = DeveloperSession.objects.all()

        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if start_date:
            from dateutil.parser import parse

            start_date_parsed = parse(start_date)
            queryset = queryset.filter(session_start__gte=start_date_parsed)
        if end_date:
            from dateutil.parser import parse

            end_date_parsed = parse(end_date)
            queryset = queryset.filter(session_start__lte=end_date_parsed)

        sessions = queryset.order_by("-session_start")[:100]  # Limit to 100 recent sessions
        serializer = DeveloperSessionSerializer(sessions, many=True)

        return Response({"sessions": serializer.data, "count": len(serializer.data)}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error getting sessions for analytics: {e}")
        return Response({"error": "Failed to get sessions"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=["Metrics"],
    summary="Get all code metrics for analytics",
    description="Get code metrics for analytics - API endpoint",
    parameters=[
        OpenApiParameter(name="user_id", description="User ID to filter metrics", type=OpenApiTypes.STR),
        OpenApiParameter(name="project_id", description="Project ID to filter metrics", type=OpenApiTypes.STR),
        OpenApiParameter(name="start_date", description="Start date for filtering", type=OpenApiTypes.DATETIME),
        OpenApiParameter(name="end_date", description="End date for filtering", type=OpenApiTypes.DATETIME),
    ],
    responses={
        200: {
            "description": "List of code metrics",
            "content": {"application/json": {"schema": {"description": "List of code metrics"}}},
        }
    },
)
@api_view(["GET"])
@permission_classes([AllowAny])
def get_all_code_metrics(request):
    """Get code metrics for analytics - API endpoint"""
    try:
        user_id = request.GET.get("user_id")
        project_id = request.GET.get("project_id")
        start_date = request.GET.get("start_date")
        end_date = request.GET.get("end_date")

        queryset = CodeMetrics.objects.all()

        if user_id:
            # Filter by sessions that belong to the user
            queryset = queryset.filter(session__user_id=user_id)
        if project_id:
            # Filter by project_id field directly (more efficient than text search)
            queryset = queryset.filter(project_id=project_id)
        if start_date:
            from dateutil.parser import parse

            start_date_parsed = parse(start_date)
            queryset = queryset.filter(calculated_at__gte=start_date_parsed)
        if end_date:
            from dateutil.parser import parse

            end_date_parsed = parse(end_date)
            queryset = queryset.filter(calculated_at__lte=end_date_parsed)

        metrics = queryset.order_by("-calculated_at")[:100]  # Limit to 100 recent metrics
        serializer = CodeMetricsSerializer(metrics, many=True)

        return Response({"results": serializer.data, "count": len(serializer.data)}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error getting code metrics for analytics: {e}")
        return Response({"error": "Failed to get code metrics"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=["API - Git Events"],
    summary="Get git events by repository",
    description="Get git events filtered by repository URL for cross-service synchronization",
    parameters=[
        OpenApiParameter(
            name="repository_url",
            description="Repository URL to filter events (e.g., https://github.com/owner/repo)",
            type=OpenApiTypes.STR,
            required=True,
        ),
        OpenApiParameter(name="event_type", description="Filter by event type (commit, push, etc.)", type=OpenApiTypes.STR),
        OpenApiParameter(name="branch", description="Filter by branch name", type=OpenApiTypes.STR),
        OpenApiParameter(name="since", description="Get events since this timestamp (ISO format)", type=OpenApiTypes.DATETIME),
        OpenApiParameter(name="limit", description="Maximum number of events to return (default 100)", type=OpenApiTypes.INT),
    ],
    responses={
        200: {
            "description": "List of git events",
            "content": {"application/json": {"schema": {"description": "List of git events"}}},
        }
    },
)
@api_view(["GET"])
@permission_classes([AllowAny])  # For service-to-service communication
def get_git_events_by_repository(request):
    """Get git events filtered by repository URL for management service synchronization."""
    try:
        repository_url = request.GET.get("repository_url")
        if not repository_url:
            return Response({"error": "repository_url parameter is required"}, status=status.HTTP_400_BAD_REQUEST)

        event_type = request.GET.get("event_type")
        branch = request.GET.get("branch")
        since = request.GET.get("since")
        limit = int(request.GET.get("limit", 100))

        # Normalize repository URL (remove .git suffix if present)
        normalized_url = repository_url.rstrip("/")
        if normalized_url.endswith(".git"):
            normalized_url = normalized_url[:-4]

        # Build query - filter by remote_name which contains the repository URL
        queryset = GitEvent.objects.filter(
            models.Q(remote_name__icontains=normalized_url) | models.Q(git_metadata__repository_url__icontains=normalized_url)
        )

        # Only get commit events for CodeCommit synchronization
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        else:
            # Default to commit events for sync
            queryset = queryset.filter(event_type="commit")

        if branch:
            queryset = queryset.filter(branch_name=branch)

        if since:
            from dateutil.parser import parse

            since_parsed = parse(since)
            queryset = queryset.filter(timestamp__gte=since_parsed)

        # Order by timestamp descending and limit results
        git_events = queryset.order_by("-timestamp")[:limit]
        serializer = GitEventSerializer(git_events, many=True)

        return Response(
            {
                "git_events": serializer.data,
                "count": len(serializer.data),
                "repository_url": repository_url,
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.error(f"Error getting git events by repository: {e}")
        return Response({"error": "Failed to get git events"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
