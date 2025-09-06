from django.contrib import admin

from .admin_auth import monitoring_admin_site
from .models import ActivityLog, CodeMetrics, DeveloperSession, GitEvent


class DeveloperSessionAdmin(admin.ModelAdmin):
    list_display = ("session_id", "user_id", "ide_name", "session_start", "session_end", "is_active")
    list_filter = ("ide_name", "operating_system", "session_start")
    search_fields = ("user_id", "ide_name", "git_repository_url")
    readonly_fields = ("session_id", "created_at", "updated_at", "session_duration_minutes")
    ordering = ("-created_at",)


class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("log_id", "session", "activity_type", "timestamp", "file_path")
    list_filter = ("activity_type", "file_extension", "timestamp")
    search_fields = ("session__session_id", "file_path")
    readonly_fields = ("log_id", "created_at")
    ordering = ("-timestamp",)


class CodeMetricsAdmin(admin.ModelAdmin):
    list_display = ("metrics_id", "session", "file_path", "lines_of_code", "total_changes", "calculated_at")
    list_filter = ("file_extension", "calculated_at")
    search_fields = ("session__session_id", "file_path")
    readonly_fields = ("metrics_id", "created_at")
    ordering = ("-calculated_at",)


class GitEventAdmin(admin.ModelAdmin):
    list_display = ("event_id", "session", "event_type", "commit_hash", "branch_name", "timestamp")
    list_filter = ("event_type", "branch_name", "timestamp")
    search_fields = ("session__session_id", "commit_hash", "commit_message", "author_email")
    readonly_fields = ("event_id", "created_at")
    ordering = ("-timestamp",)


# Register models with both the default admin and custom admin
admin.site.register(DeveloperSession, DeveloperSessionAdmin)
admin.site.register(ActivityLog, ActivityLogAdmin)
admin.site.register(CodeMetrics, CodeMetricsAdmin)
admin.site.register(GitEvent, GitEventAdmin)

# Also register with custom admin site
monitoring_admin_site.register(DeveloperSession, DeveloperSessionAdmin)
monitoring_admin_site.register(ActivityLog, ActivityLogAdmin)
monitoring_admin_site.register(CodeMetrics, CodeMetricsAdmin)
monitoring_admin_site.register(GitEvent, GitEventAdmin)
