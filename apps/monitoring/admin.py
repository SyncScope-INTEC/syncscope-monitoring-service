from django.contrib import admin
from .models import DeveloperSession, ActivityLog, CodeMetrics, GitEvent


@admin.register(DeveloperSession)
class DeveloperSessionAdmin(admin.ModelAdmin):
    list_display = ('session_id', 'user_id', 'ide_name', 'session_start', 'session_end', 'is_active')
    list_filter = ('ide_name', 'operating_system', 'session_start')
    search_fields = ('user_id', 'ide_name', 'git_repository_url')
    readonly_fields = ('session_id', 'created_at', 'updated_at', 'session_duration_minutes')
    ordering = ('-created_at',)


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('log_id', 'session', 'activity_type', 'timestamp', 'file_path')
    list_filter = ('activity_type', 'file_extension', 'timestamp')
    search_fields = ('session__session_id', 'file_path')
    readonly_fields = ('log_id', 'created_at')
    ordering = ('-timestamp',)


@admin.register(CodeMetrics)
class CodeMetricsAdmin(admin.ModelAdmin):
    list_display = ('metrics_id', 'session', 'file_path', 'lines_of_code', 'total_changes', 'calculated_at')
    list_filter = ('file_extension', 'calculated_at')
    search_fields = ('session__session_id', 'file_path')
    readonly_fields = ('metrics_id', 'created_at')
    ordering = ('-calculated_at',)


@admin.register(GitEvent)
class GitEventAdmin(admin.ModelAdmin):
    list_display = ('event_id', 'session', 'event_type', 'commit_hash', 'branch_name', 'timestamp')
    list_filter = ('event_type', 'branch_name', 'timestamp')
    search_fields = ('session__session_id', 'commit_hash', 'commit_message', 'author_email')
    readonly_fields = ('event_id', 'created_at')
    ordering = ('-timestamp',)