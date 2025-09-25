"""
URL configuration for syncscope-monitoring-service project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from apps.monitoring.debug_views import test_auth_service, test_settings
from apps.monitoring.health import health_check, simple_health_check
from apps.monitoring.views import api_get_code_metrics, api_get_sessions, api_home

urlpatterns = [
    # Home page
    path("", api_home, name="api_home"),
    # Health check endpoints
    path("health/", health_check, name="health_check_root"),
    path("simple-health/", simple_health_check, name="simple_health"),
    path("admin/", admin.site.urls),
    path("monitoring/", include("apps.monitoring.urls")),  # Include monitoring URLs with prefix
    # API endpoints for analytics service integration
    path("api/sessions/", api_get_sessions, name="api_sessions"),
    path("api/code-metrics/", api_get_code_metrics, name="api_code_metrics"),
    # API Documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

# Serve static files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
