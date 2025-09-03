from rest_framework import serializers

from .models import ActivityLog, CodeMetrics, DeveloperSession, GitEvent
from .validators import (
    ActivityTypeValidator,
    FileExtensionValidator,
    FilePathValidator,
    GitBranchValidator,
    GitEventTypeValidator,
    GitHashValidator,
    IDENameValidator,
    SessionMetadataValidator,
    validate_complexity_score,
    validate_positive_integer,
    validate_reasonable_line_count,
)


class DeveloperSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeveloperSession
        fields = [
            "session_id",
            "user_id",
            "session_start",
            "session_end",
            "session_duration_minutes",
            "ide_name",
            "ide_version",
            "project_path",
            "git_repository_url",
            "git_branch",
            "git_commit_hash",
            "operating_system",
            "session_metadata",
        ]
        read_only_fields = ["session_id", "session_duration_minutes", "created_at", "updated_at"]


class SessionStartSerializer(serializers.ModelSerializer):
    ide_name = serializers.CharField(validators=[IDENameValidator()])
    project_path = serializers.CharField(required=False, allow_blank=True, validators=[FilePathValidator()])
    git_branch = serializers.CharField(required=False, allow_blank=True, validators=[GitBranchValidator()])
    git_commit_hash = serializers.CharField(required=False, allow_blank=True, validators=[GitHashValidator()])
    session_metadata = serializers.JSONField(required=False, validators=[SessionMetadataValidator()])

    class Meta:
        model = DeveloperSession
        fields = [
            "user_id",
            "ide_name",
            "ide_version",
            "project_path",
            "git_repository_url",
            "git_branch",
            "git_commit_hash",
            "operating_system",
            "session_metadata",
        ]

    def validate_user_id(self, value):
        if value <= 0:
            raise serializers.ValidationError("User ID must be a positive integer")
        return value


class SessionEndSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    session_metadata = serializers.JSONField(required=False)


class ActivityLogSerializer(serializers.ModelSerializer):
    activity_type = serializers.CharField(validators=[ActivityTypeValidator()])
    file_path = serializers.CharField(required=False, allow_blank=True, validators=[FilePathValidator()])
    activity_metadata = serializers.JSONField(required=False, validators=[SessionMetadataValidator()])

    class Meta:
        model = ActivityLog
        fields = ["log_id", "session", "activity_type", "timestamp", "file_path", "file_extension", "activity_metadata"]
        read_only_fields = ["log_id", "file_extension", "created_at"]


class CodeMetricsSerializer(serializers.ModelSerializer):
    total_changes = serializers.ReadOnlyField()
    file_path = serializers.CharField(validators=[FilePathValidator()])
    lines_of_code = serializers.IntegerField(validators=[validate_positive_integer, validate_reasonable_line_count])
    lines_added = serializers.IntegerField(validators=[validate_positive_integer, validate_reasonable_line_count])
    lines_deleted = serializers.IntegerField(validators=[validate_positive_integer, validate_reasonable_line_count])
    lines_modified = serializers.IntegerField(validators=[validate_positive_integer, validate_reasonable_line_count])
    complexity_score = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True, validators=[validate_complexity_score]
    )
    function_count = serializers.IntegerField(required=False, allow_null=True, validators=[validate_positive_integer])
    class_count = serializers.IntegerField(required=False, allow_null=True, validators=[validate_positive_integer])
    comment_lines = serializers.IntegerField(
        required=False, allow_null=True, validators=[validate_positive_integer, validate_reasonable_line_count]
    )
    blank_lines = serializers.IntegerField(
        required=False, allow_null=True, validators=[validate_positive_integer, validate_reasonable_line_count]
    )
    metrics_metadata = serializers.JSONField(required=False, validators=[SessionMetadataValidator()])

    class Meta:
        model = CodeMetrics
        fields = [
            "metrics_id",
            "session",
            "file_path",
            "file_extension",
            "lines_of_code",
            "lines_added",
            "lines_deleted",
            "lines_modified",
            "complexity_score",
            "function_count",
            "class_count",
            "comment_lines",
            "blank_lines",
            "metrics_metadata",
            "calculated_at",
            "total_changes",
        ]
        read_only_fields = ["metrics_id", "file_extension", "total_changes", "created_at"]


class GitEventSerializer(serializers.ModelSerializer):
    net_changes = serializers.ReadOnlyField()
    event_type = serializers.CharField(validators=[GitEventTypeValidator()])
    commit_hash = serializers.CharField(required=False, allow_blank=True, validators=[GitHashValidator()])
    branch_name = serializers.CharField(required=False, allow_blank=True, validators=[GitBranchValidator()])
    files_changed = serializers.IntegerField(required=False, allow_null=True, validators=[validate_positive_integer])
    insertions = serializers.IntegerField(
        required=False, allow_null=True, validators=[validate_positive_integer, validate_reasonable_line_count]
    )
    deletions = serializers.IntegerField(
        required=False, allow_null=True, validators=[validate_positive_integer, validate_reasonable_line_count]
    )
    git_metadata = serializers.JSONField(required=False, validators=[SessionMetadataValidator()])

    class Meta:
        model = GitEvent
        fields = [
            "event_id",
            "session",
            "event_type",
            "timestamp",
            "commit_hash",
            "commit_message",
            "branch_name",
            "remote_name",
            "files_changed",
            "insertions",
            "deletions",
            "author_name",
            "author_email",
            "git_metadata",
            "net_changes",
        ]
        read_only_fields = ["event_id", "net_changes", "created_at"]

    def validate_author_email(self, value):
        if value:
            from django.core.validators import validate_email

            validate_email(value)
        return value


class BulkActivitySerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    activities = ActivityLogSerializer(many=True)

    def validate_activities(self, value):
        """Validate activities list is not empty and has reasonable size."""
        if not value:
            raise serializers.ValidationError("Activities list cannot be empty")
        if len(value) > 1000:  # Reasonable bulk limit
            raise serializers.ValidationError("Too many activities in bulk request (max 1000)")
        return value
