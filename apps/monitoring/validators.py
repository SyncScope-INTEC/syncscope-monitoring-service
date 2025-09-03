"""
Custom validators for monitoring service input data.
"""

import os
import re

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from rest_framework import serializers


class FilePathValidator:
    """Validate file paths for security and format."""

    def __init__(self, max_length=1000):
        self.max_length = max_length

    def __call__(self, value):
        if not value:
            return

        if len(value) > self.max_length:
            raise ValidationError(f"File path too long (max {self.max_length} characters)")

        # Check for potentially dangerous paths
        dangerous_patterns = [
            r"\.\.",  # Directory traversal
            r'[<>:"|?*]',  # Windows invalid characters
            r"^[/\\]*(etc|proc|sys|dev)",  # System directories (Unix)
            r"^[A-Za-z]:[/\\]*(?:Windows|System32|Program Files)",  # System directories (Windows)
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                raise ValidationError("File path contains potentially dangerous elements")


class GitHashValidator:
    """Validate Git commit hashes."""

    def __call__(self, value):
        if not value:
            return

        # Git hash should be 7-40 hexadecimal characters
        if not re.match(r"^[a-f0-9]{7,40}$", value, re.IGNORECASE):
            raise ValidationError("Invalid Git commit hash format")


class GitBranchValidator:
    """Validate Git branch names."""

    def __call__(self, value):
        if not value:
            return

        # Basic Git branch name validation
        if len(value) > 255:
            raise ValidationError("Branch name too long (max 255 characters)")

        # Git branch name rules
        invalid_patterns = [
            r"^/",  # Cannot start with /
            r"/$",  # Cannot end with /
            r"//",  # Cannot have consecutive /
            r"\.\.",  # Cannot contain ..
            r"[~^:?*\[\\\s]",  # Invalid characters
            r"^-",  # Cannot start with -
            r"\.$",  # Cannot end with .
        ]

        for pattern in invalid_patterns:
            if re.search(pattern, value):
                raise ValidationError("Invalid Git branch name format")


class IDENameValidator:
    """Validate IDE names."""

    ALLOWED_IDES = {
        "vscode",
        "visual studio code",
        "intellij",
        "intellij idea",
        "pycharm",
        "webstorm",
        "phpstorm",
        "rubymine",
        "clion",
        "datagrip",
        "goland",
        "rider",
        "appcode",
        "android studio",
        "eclipse",
        "netbeans",
        "sublime text",
        "atom",
        "vim",
        "neovim",
        "emacs",
        "notepad++",
        "brackets",
        "code",
        "xcode",
        "unity",
        "unreal engine",
        "blender",
    }

    def __call__(self, value):
        if not value:
            raise ValidationError("IDE name is required")

        if len(value) > 100:
            raise ValidationError("IDE name too long (max 100 characters)")

        # Allow custom IDEs but log them for review
        normalized = value.lower().strip()
        if normalized not in self.ALLOWED_IDES:
            # Log unknown IDE for review but don't reject
            import logging

            logger = logging.getLogger("apps.monitoring.validators")
            logger.info(f"Unknown IDE detected: {value}")


class SessionMetadataValidator:
    """Validate session metadata JSON structure."""

    MAX_KEYS = 50
    MAX_VALUE_LENGTH = 1000
    MAX_NESTED_DEPTH = 3

    def __call__(self, value):
        if not value:
            return

        if not isinstance(value, dict):
            raise ValidationError("Session metadata must be a JSON object")

        self._validate_dict(value, depth=0)

    def _validate_dict(self, data, depth=0):
        if depth > self.MAX_NESTED_DEPTH:
            raise ValidationError(f"Session metadata too deeply nested (max {self.MAX_NESTED_DEPTH} levels)")

        if len(data) > self.MAX_KEYS:
            raise ValidationError(f"Too many keys in metadata (max {self.MAX_KEYS})")

        for key, value in data.items():
            if not isinstance(key, str):
                raise ValidationError("All metadata keys must be strings")

            if len(key) > 100:
                raise ValidationError("Metadata key too long (max 100 characters)")

            if isinstance(value, dict):
                self._validate_dict(value, depth + 1)
            elif isinstance(value, (list, tuple)):
                self._validate_list(value, depth + 1)
            elif isinstance(value, str) and len(value) > self.MAX_VALUE_LENGTH:
                raise ValidationError(f"Metadata value too long (max {self.MAX_VALUE_LENGTH} characters)")

    def _validate_list(self, data, depth):
        if len(data) > 100:  # Reasonable list size limit
            raise ValidationError("Metadata list too long (max 100 items)")

        for item in data:
            if isinstance(item, dict):
                self._validate_dict(item, depth + 1)
            elif isinstance(item, str) and len(item) > self.MAX_VALUE_LENGTH:
                raise ValidationError(f"Metadata list item too long (max {self.MAX_VALUE_LENGTH} characters)")


class ActivityTypeValidator:
    """Validate activity types."""

    def __call__(self, value):
        from .models import ActivityLog

        valid_choices = [choice[0] for choice in ActivityLog.ACTIVITY_TYPE_CHOICES]
        if value not in valid_choices:
            raise ValidationError(f'Invalid activity type. Must be one of: {", ".join(valid_choices)}')


class GitEventTypeValidator:
    """Validate git event types."""

    def __call__(self, value):
        from .models import GitEvent

        valid_choices = [choice[0] for choice in GitEvent.EVENT_TYPE_CHOICES]
        if value not in valid_choices:
            raise ValidationError(f'Invalid git event type. Must be one of: {", ".join(valid_choices)}')


class FileExtensionValidator:
    """Validate file extensions."""

    COMMON_EXTENSIONS = {
        "py",
        "js",
        "ts",
        "jsx",
        "tsx",
        "java",
        "cpp",
        "c",
        "h",
        "hpp",
        "cs",
        "go",
        "rs",
        "php",
        "rb",
        "swift",
        "kt",
        "scala",
        "clj",
        "html",
        "css",
        "scss",
        "sass",
        "less",
        "xml",
        "json",
        "yaml",
        "yml",
        "toml",
        "ini",
        "cfg",
        "conf",
        "md",
        "txt",
        "sql",
        "sh",
        "bat",
        "ps1",
        "dockerfile",
        "makefile",
        "gradle",
    }

    def __call__(self, value):
        if not value:
            return

        if len(value) > 20:
            raise ValidationError("File extension too long (max 20 characters)")

        # Remove leading dot if present
        extension = value.lstrip(".")

        # Check for valid characters
        if not re.match(r"^[a-zA-Z0-9_-]+$", extension):
            raise ValidationError("File extension contains invalid characters")


def validate_positive_integer(value):
    """Validate positive integers."""
    if value is not None and value < 0:
        raise ValidationError("Value must be positive or zero")


def validate_reasonable_line_count(value):
    """Validate reasonable line counts for code metrics."""
    if value is not None and value > 1000000:  # 1 million lines
        raise ValidationError("Line count seems unreasonably high (max 1,000,000)")


def validate_complexity_score(value):
    """Validate complexity scores."""
    if value is not None and (value < 0 or value > 1000):
        raise ValidationError("Complexity score must be between 0 and 1000")
