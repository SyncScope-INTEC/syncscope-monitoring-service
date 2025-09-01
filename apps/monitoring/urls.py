from django.urls import path
from . import views

urlpatterns = [
    # Health check
    path("health/", views.health_check, name="health_check"),
    
    # Session endpoints
    path("sessions/start/", views.start_session, name="start_session"),
    path("sessions/end/", views.end_session, name="end_session"),
    path("sessions/<int:user_id>/", views.get_user_sessions, name="get_user_sessions"),
    
    # Activity endpoints
    path("activities/bulk/", views.bulk_activities, name="bulk_activities"),
    
    # Metrics endpoints
    path("metrics/code/", views.submit_code_metrics, name="submit_code_metrics"),
    
    # Events endpoints
    path("events/git/", views.record_git_event, name="record_git_event"),
]