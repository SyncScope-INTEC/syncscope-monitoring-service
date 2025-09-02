"""
Class-based views with enhanced mixins.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema
from django.utils import timezone

from .mixins import PerformanceMonitoringMixin, CacheHealthCheck
from .db_mixins import ServerlessViewMixin
from config.database_retry import DatabaseHealthCheck
from .permissions import IsAuthenticated, CanAccessUserData
from .models import DeveloperSession
from .serializers import DeveloperSessionSerializer


class BaseMonitoringAPIView(ServerlessViewMixin, PerformanceMonitoringMixin, APIView):
    """
    Base API view with database resilience and performance monitoring.
    """
    permission_classes = [IsAuthenticated]


class SessionStatsView(BaseMonitoringAPIView):
    """
    Get session statistics with health-aware handling.
    """
    permission_classes = [CanAccessUserData]
    
    @extend_schema(
        tags=['Sessions'],
        responses={200: {
            'description': 'Session statistics',
            'example': {
                'total_sessions': 150,
                'active_sessions': 5,
                'total_duration_hours': 245.5,
                'avg_session_duration_minutes': 65.2,
                'last_session': '2024-01-01T10:00:00Z'
            }
        }}
    )
    def get(self, request, user_id):
        """Get comprehensive session statistics for a user."""
        from django.db.models import Count, Sum, Avg
        
        # Get session statistics
        sessions = DeveloperSession.objects.filter(user_id=user_id)
        
        stats = sessions.aggregate(
            total_sessions=Count('session_id'),
            total_duration=Sum('session_duration_minutes'),
            avg_duration=Avg('session_duration_minutes')
        )
        
        active_sessions = sessions.filter(session_end__isnull=True).count()
        
        last_session = sessions.order_by('-session_start').first()
        
        response_data = {
            'user_id': user_id,
            'total_sessions': stats['total_sessions'] or 0,
            'active_sessions': active_sessions,
            'total_duration_hours': round((stats['total_duration'] or 0) / 60, 1),
            'avg_session_duration_minutes': round(stats['avg_duration'] or 0, 1),
            'last_session': last_session.session_start.isoformat() if last_session else None,
            'generated_at': timezone.now().isoformat()
        }
        
        return Response(response_data, status=status.HTTP_200_OK)


class HealthMetricsView(BaseMonitoringAPIView):
    """
    Detailed health metrics endpoint.
    """
    permission_classes = []  # Allow unauthenticated access
    
    @extend_schema(
        tags=['Health'],
        responses={200: {
            'description': 'Detailed health metrics',
            'example': {
                'service': 'syncscope-monitoring-service',
                'status': 'healthy',
                'uptime_seconds': 3600,
                'database': {'status': 'healthy', 'response_time_ms': 5.2},
                'redis': {'status': 'healthy', 'response_time_ms': 1.1},
                'system': {'memory_usage': '45%', 'cpu_usage': '12%'}
            }
        }}
    )
    def get(self, request):
        """Get detailed health metrics."""
        import time
        import psutil
        import os
        from django.conf import settings
        
        start_time = time.time()
        
        # Database health with timing
        db_start = time.time()
        try:
            db_healthy = DatabaseHealthCheck.is_healthy(use_cache=False)
            db_response_time = round((time.time() - db_start) * 1000, 1)
            database_status = {
                'status': 'healthy' if db_healthy else 'unhealthy',
                'response_time_ms': db_response_time
            }
        except Exception as e:
            database_status = {
                'status': 'error',
                'error': str(e),
                'response_time_ms': round((time.time() - db_start) * 1000, 1)
            }
        
        # Redis health with timing
        redis_start = time.time()
        try:
            redis_healthy = CacheHealthCheck.is_healthy()
            redis_response_time = round((time.time() - redis_start) * 1000, 1)
            redis_status = {
                'status': 'healthy' if redis_healthy else 'unhealthy',
                'response_time_ms': redis_response_time
            }
        except Exception as e:
            redis_status = {
                'status': 'error',
                'error': str(e),
                'response_time_ms': round((time.time() - redis_start) * 1000, 1)
            }
        
        # System metrics (if psutil is available)
        system_metrics = {}
        try:
            system_metrics = {
                'memory_usage': f"{psutil.virtual_memory().percent}%",
                'cpu_usage': f"{psutil.cpu_percent()}%",
                'disk_usage': f"{psutil.disk_usage('/').percent}%"
            }
        except (ImportError, Exception):
            system_metrics = {'status': 'metrics_unavailable'}
        
        # Process info
        process_info = {
            'pid': os.getpid(),
            'python_version': f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
            'django_version': getattr(settings, 'DJANGO_VERSION', 'unknown')
        }
        
        overall_healthy = (
            database_status['status'] == 'healthy' and
            redis_status['status'] == 'healthy'
        )
        
        response_data = {
            'service': 'syncscope-monitoring-service',
            'version': getattr(settings, 'VERSION', '1.0.0'),
            'status': 'healthy' if overall_healthy else 'unhealthy',
            'timestamp': timezone.now().isoformat(),
            'response_time_ms': round((time.time() - start_time) * 1000, 1),
            'database': database_status,
            'redis': redis_status,
            'system': system_metrics,
            'process': process_info
        }
        
        status_code = status.HTTP_200_OK if overall_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(response_data, status=status_code)