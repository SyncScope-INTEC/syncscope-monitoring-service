from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from .permissions import IsAuthenticated, CanAccessUserData
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.openapi import OpenApiTypes
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import DeveloperSession, ActivityLog, CodeMetrics, GitEvent
from .serializers import (
    DeveloperSessionSerializer, SessionStartSerializer, SessionEndSerializer,
    BulkActivitySerializer, ActivityLogSerializer, CodeMetricsSerializer, GitEventSerializer
)
from .auth_utils import get_user_from_request
from .redis_client import RedisClient
from .decorators import (
    health_ratelimit, session_ratelimit, activity_ratelimit, 
    metrics_ratelimit, git_events_ratelimit
)
from .logging_utils import monitoring_logger
from .tasks import process_session_analytics

import logging

logger = logging.getLogger(__name__)


@extend_schema(
    tags=['Health'],
    responses={200: {'description': 'Service health status'}}
)
@api_view(["GET"])
@permission_classes([AllowAny])
@health_ratelimit
def health_check(request):
    return Response({"status": "healthy", "service": "syncscope-monitoring-service"}, status=status.HTTP_200_OK)


@extend_schema(
    tags=['Sessions'],
    request=SessionStartSerializer,
    responses={201: DeveloperSessionSerializer},
    description='Start a new developer monitoring session'
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
                'session_id': str(session.session_id),
                'user_id': session.user_id,
                'started_at': session.session_start.isoformat(),
            }
            redis_client.set_session_data(str(session.session_id), session_data)
            
            response_serializer = DeveloperSessionSerializer(session)
            monitoring_logger.log_session_event(
                'started', session.session_id, session.user_id,
                ide_name=session.ide_name, project_path=session.project_path
            )
            
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.error(f"Error starting session: {e}")
        return Response(
            {"error": "Failed to start session"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Sessions'],
    request=SessionEndSerializer,
    responses={200: DeveloperSessionSerializer},
    description='End an existing developer monitoring session'
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@session_ratelimit
def end_session(request):
    """End an existing developer monitoring session."""
    try:
        serializer = SessionEndSerializer(data=request.data)
        if serializer.is_valid():
            session_id = serializer.validated_data['session_id']
            session_metadata = serializer.validated_data.get('session_metadata', {})
            
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
                    'ended', session_id, session.user_id,
                    duration_minutes=session.session_duration_minutes
                )
                
                # Trigger analytics processing in background
                process_session_analytics.delay(str(session_id))
            
            response_serializer = DeveloperSessionSerializer(session)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.error(f"Error ending session: {e}")
        return Response(
            {"error": "Failed to end session"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Activities'],
    request=BulkActivitySerializer,
    responses={201: {'description': 'Activities created successfully'}},
    description='Bulk upload developer activities for a session'
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@activity_ratelimit
def bulk_activities(request):
    """Bulk upload developer activities for a session."""
    try:
        serializer = BulkActivitySerializer(data=request.data)
        if serializer.is_valid():
            session_id = serializer.validated_data['session_id']
            activities_data = serializer.validated_data['activities']
            
            # Verify session exists
            session = get_object_or_404(DeveloperSession, session_id=session_id)
            
            # Create activities in bulk
            activities = []
            for activity_data in activities_data:
                # Remove session from data as we'll set it explicitly
                activity_data.pop('session', None)
                activity = ActivityLog(session=session, **activity_data)
                activities.append(activity)
            
            # Bulk create for better performance
            created_activities = ActivityLog.objects.bulk_create(activities)
            
            monitoring_logger.log_activity_event(
                'bulk_upload', session_id, count=len(created_activities)
            )
            
            return Response({
                "message": f"Successfully created {len(created_activities)} activities",
                "session_id": str(session_id),
                "activities_count": len(created_activities)
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.error(f"Error creating bulk activities: {e}")
        return Response(
            {"error": "Failed to create activities"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Sessions'],
    parameters=[
        OpenApiParameter(
            name='user_id',
            description='User ID to get sessions for',
            required=True,
            type=OpenApiTypes.INT,
            location=OpenApiParameter.PATH
        ),
        OpenApiParameter(
            name='limit',
            description='Number of sessions to return (default: 20, max: 100)',
            required=False,
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY
        ),
        OpenApiParameter(
            name='offset',
            description='Number of sessions to skip',
            required=False,
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY
        ),
        OpenApiParameter(
            name='active_only',
            description='Return only active sessions',
            required=False,
            type=OpenApiTypes.BOOL,
            location=OpenApiParameter.QUERY
        )
    ],
    responses={200: DeveloperSessionSerializer(many=True)},
    description='Get developer sessions for a specific user'
)
@api_view(["GET"])
@permission_classes([CanAccessUserData])
@session_ratelimit
def get_user_sessions(request, user_id):
    """Get developer sessions for a specific user."""
    try:
        # Parse query parameters
        limit = min(int(request.GET.get('limit', 20)), 100)  # Max 100
        offset = int(request.GET.get('offset', 0))
        active_only = request.GET.get('active_only', 'false').lower() == 'true'
        
        # Build queryset
        queryset = DeveloperSession.objects.filter(user_id=user_id)
        
        if active_only:
            queryset = queryset.filter(session_end__isnull=True)
        
        # Apply pagination
        total_count = queryset.count()
        sessions = queryset[offset:offset + limit]
        
        # Check Redis for active session data
        redis_client = RedisClient()
        serializer_data = []
        
        for session in sessions:
            session_data = DeveloperSessionSerializer(session).data
            
            # Add Redis cache data for active sessions
            if session.is_active:
                cached_data = redis_client.get_session_data(str(session.session_id))
                if cached_data:
                    session_data['cached_data'] = cached_data
            
            serializer_data.append(session_data)
        
        response_data = {
            "count": total_count,
            "next": None,
            "previous": None,
            "results": serializer_data
        }
        
        # Add pagination links
        if offset + limit < total_count:
            response_data["next"] = f"?limit={limit}&offset={offset + limit}"
        if offset > 0:
            response_data["previous"] = f"?limit={limit}&offset={max(0, offset - limit)}"
        
        logger.info(f"Retrieved {len(sessions)} sessions for user {user_id}")
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    except ValueError as e:
        return Response(
            {"error": "Invalid parameter format"}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Error retrieving user sessions: {e}")
        return Response(
            {"error": "Failed to retrieve sessions"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Metrics'],
    request=CodeMetricsSerializer,
    responses={201: CodeMetricsSerializer},
    description='Submit code metrics for a file in a session'
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
            session_id = serializer.validated_data['session'].session_id
            session = get_object_or_404(DeveloperSession, session_id=session_id)
            
            # Check if metrics already exist for this file in this session
            existing_metrics = CodeMetrics.objects.filter(
                session=session,
                file_path=serializer.validated_data['file_path']
            ).first()
            
            if existing_metrics:
                # Update existing metrics
                for field, value in serializer.validated_data.items():
                    if field != 'session':  # Don't update the session
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
                    'file_path': metrics.file_path,
                    'lines_of_code': metrics.lines_of_code,
                    'total_changes': metrics.total_changes,
                    'calculated_at': metrics.calculated_at.isoformat()
                }
                redis_client.set_metrics_cache(session.user_id, metrics_data)
                
                response_serializer = CodeMetricsSerializer(metrics)
                logger.info(f"Created code metrics for {metrics.file_path} in session {session_id}")
                
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.error(f"Error submitting code metrics: {e}")
        return Response(
            {"error": "Failed to submit code metrics"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Events'],
    request=GitEventSerializer,
    responses={201: GitEventSerializer},
    description='Record a git event for a session'
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
            session_id = serializer.validated_data['session'].session_id
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
                repo_url = git_event.git_metadata.get('repository_url')
                if repo_url:
                    session.git_repository_url = repo_url
            
            session.save()
            
            # Log activity for git event
            ActivityLog.objects.create(
                session=session,
                activity_type=f"git_{git_event.event_type}",
                timestamp=git_event.timestamp,
                activity_metadata={
                    'git_event_id': str(git_event.event_id),
                    'commit_hash': git_event.commit_hash,
                    'branch_name': git_event.branch_name
                }
            )
            
            response_serializer = GitEventSerializer(git_event)
            logger.info(f"Recorded git event {git_event.event_type} for session {session_id}")
            
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.error(f"Error recording git event: {e}")
        return Response(
            {"error": "Failed to record git event"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )