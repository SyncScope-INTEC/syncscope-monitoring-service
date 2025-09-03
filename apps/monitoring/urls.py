from django.urls import path

from . import views
from .class_views import HealthMetricsView, SessionStatsView

urlpatterns = [
    # Health endpoints
    path("health/", views.health_check, name="health_check"),
    path("health/live/", views.liveness_check, name="liveness_check"),
    path("health/ready/", views.readiness_check, name="readiness_check"),
    path("health/metrics/", HealthMetricsView.as_view(), name="health_metrics"),
    # Session endpoints
    path("sessions/start/", views.start_session, name="start_session"),
    path("sessions/end/", views.end_session, name="end_session"),
    path("sessions/<int:user_id>/", views.get_user_sessions, name="get_user_sessions"),
    path("sessions/<int:user_id>/stats/", SessionStatsView.as_view(), name="session_stats"),
    # Activity endpoints
    path("activities/bulk/", views.bulk_activities, name="bulk_activities"),
    # Metrics endpoints
    path("metrics/code/", views.submit_code_metrics, name="submit_code_metrics"),
    # Events endpoints
    path("events/git/", views.record_git_event, name="record_git_event"),
]
