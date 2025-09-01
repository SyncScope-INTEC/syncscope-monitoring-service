from django.db import models
from django.utils import timezone
import uuid


class DeveloperSession(models.Model):
    """
    Model representing a developer monitoring session.
    Maps to the monitoring.developer_sessions table.
    """
    session_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.IntegerField(help_text="Reference to auth.users.user_id")
    session_start = models.DateTimeField(default=timezone.now)
    session_end = models.DateTimeField(null=True, blank=True)
    session_duration_minutes = models.IntegerField(null=True, blank=True)
    ide_name = models.CharField(max_length=100)
    ide_version = models.CharField(max_length=50, null=True, blank=True)
    project_path = models.TextField(null=True, blank=True)
    git_repository_url = models.URLField(null=True, blank=True)
    git_branch = models.CharField(max_length=255, null=True, blank=True)
    git_commit_hash = models.CharField(max_length=40, null=True, blank=True)
    operating_system = models.CharField(max_length=50, null=True, blank=True)
    session_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'monitoring.developer_sessions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user_id']),
            models.Index(fields=['session_start']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Session {self.session_id} - User {self.user_id}"

    def save(self, *args, **kwargs):
        """Calculate session duration if session_end is set."""
        if self.session_end and self.session_start:
            duration = self.session_end - self.session_start
            self.session_duration_minutes = int(duration.total_seconds() / 60)
        super().save(*args, **kwargs)

    @property
    def is_active(self):
        """Check if session is currently active."""
        return self.session_end is None

    def end_session(self):
        """End the current session."""
        if not self.session_end:
            self.session_end = timezone.now()
            self.save()


class ActivityLog(models.Model):
    """
    Model representing developer activity logs.
    Maps to the monitoring.activity_logs table.
    """
    ACTIVITY_TYPE_CHOICES = [
        ('file_open', 'File Open'),
        ('file_edit', 'File Edit'),
        ('file_save', 'File Save'),
        ('file_close', 'File Close'),
        ('debug_start', 'Debug Start'),
        ('debug_stop', 'Debug Stop'),
        ('build_start', 'Build Start'),
        ('build_complete', 'Build Complete'),
        ('test_run', 'Test Run'),
        ('git_commit', 'Git Commit'),
        ('git_push', 'Git Push'),
        ('git_pull', 'Git Pull'),
        ('ide_focus', 'IDE Focus'),
        ('ide_blur', 'IDE Blur'),
        ('other', 'Other'),
    ]

    log_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        DeveloperSession, 
        on_delete=models.CASCADE, 
        related_name='activity_logs',
        db_column='session_id'
    )
    activity_type = models.CharField(max_length=50, choices=ACTIVITY_TYPE_CHOICES)
    timestamp = models.DateTimeField(default=timezone.now)
    file_path = models.TextField(null=True, blank=True)
    file_extension = models.CharField(max_length=20, null=True, blank=True)
    activity_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'monitoring.activity_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['session', 'timestamp']),
            models.Index(fields=['activity_type']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['file_extension']),
        ]

    def __str__(self):
        return f"{self.activity_type} - {self.timestamp}"

    def save(self, *args, **kwargs):
        """Extract file extension from file_path if provided."""
        if self.file_path and not self.file_extension:
            import os
            _, ext = os.path.splitext(self.file_path)
            self.file_extension = ext.lstrip('.')
        super().save(*args, **kwargs)


class CodeMetrics(models.Model):
    """
    Model representing code metrics for files.
    Maps to the monitoring.code_metrics table.
    """
    metrics_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        DeveloperSession, 
        on_delete=models.CASCADE, 
        related_name='code_metrics',
        db_column='session_id'
    )
    file_path = models.TextField()
    file_extension = models.CharField(max_length=20)
    lines_of_code = models.IntegerField(default=0)
    lines_added = models.IntegerField(default=0)
    lines_deleted = models.IntegerField(default=0)
    lines_modified = models.IntegerField(default=0)
    complexity_score = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    function_count = models.IntegerField(null=True, blank=True)
    class_count = models.IntegerField(null=True, blank=True)
    comment_lines = models.IntegerField(null=True, blank=True)
    blank_lines = models.IntegerField(null=True, blank=True)
    metrics_metadata = models.JSONField(default=dict, blank=True)
    calculated_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'monitoring.code_metrics'
        ordering = ['-calculated_at']
        indexes = [
            models.Index(fields=['session', 'file_path']),
            models.Index(fields=['file_extension']),
            models.Index(fields=['calculated_at']),
            models.Index(fields=['lines_of_code']),
        ]

    def __str__(self):
        return f"Metrics for {self.file_path} - {self.lines_of_code} LOC"

    @property
    def total_changes(self):
        """Calculate total lines changed."""
        return self.lines_added + self.lines_deleted + self.lines_modified

    def save(self, *args, **kwargs):
        """Extract file extension from file_path."""
        import os
        _, ext = os.path.splitext(self.file_path)
        self.file_extension = ext.lstrip('.')
        super().save(*args, **kwargs)


class GitEvent(models.Model):
    """
    Model representing git events.
    Maps to the monitoring.git_events table.
    """
    EVENT_TYPE_CHOICES = [
        ('commit', 'Commit'),
        ('push', 'Push'),
        ('pull', 'Pull'),
        ('fetch', 'Fetch'),
        ('merge', 'Merge'),
        ('rebase', 'Rebase'),
        ('checkout', 'Checkout'),
        ('branch_create', 'Branch Create'),
        ('branch_delete', 'Branch Delete'),
        ('tag_create', 'Tag Create'),
        ('tag_delete', 'Tag Delete'),
        ('stash', 'Stash'),
        ('reset', 'Reset'),
        ('cherry_pick', 'Cherry Pick'),
    ]

    event_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        DeveloperSession, 
        on_delete=models.CASCADE, 
        related_name='git_events',
        db_column='session_id'
    )
    event_type = models.CharField(max_length=50, choices=EVENT_TYPE_CHOICES)
    timestamp = models.DateTimeField(default=timezone.now)
    commit_hash = models.CharField(max_length=40, null=True, blank=True)
    commit_message = models.TextField(null=True, blank=True)
    branch_name = models.CharField(max_length=255, null=True, blank=True)
    remote_name = models.CharField(max_length=100, null=True, blank=True)
    files_changed = models.IntegerField(null=True, blank=True)
    insertions = models.IntegerField(null=True, blank=True)
    deletions = models.IntegerField(null=True, blank=True)
    author_name = models.CharField(max_length=255, null=True, blank=True)
    author_email = models.EmailField(null=True, blank=True)
    git_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'monitoring.git_events'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['session', 'timestamp']),
            models.Index(fields=['event_type']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['commit_hash']),
            models.Index(fields=['branch_name']),
        ]

    def __str__(self):
        return f"{self.event_type} - {self.commit_hash or 'N/A'} - {self.timestamp}"

    @property
    def net_changes(self):
        """Calculate net line changes."""
        if self.insertions is not None and self.deletions is not None:
            return self.insertions - self.deletions
        return None