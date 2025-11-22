"""
Tests for custom validators.
"""

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework import serializers

from ..validators import (
    ActivityTypeValidator,
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


class FilePathValidatorTest(TestCase):
    """Tests for FilePathValidator."""

    def setUp(self):
        self.validator = FilePathValidator()

    def test_valid_paths(self):
        """Test valid file paths."""
        valid_paths = [
            "/home/user/project/file.py",
            "C:\\Users\\User\\project\\file.js",
            "./relative/path/file.txt",
            "simple_file.py",
        ]

        for path in valid_paths:
            try:
                self.validator(path)
            except ValidationError:
                self.fail(f"Valid path {path} raised ValidationError")

    def test_dangerous_paths(self):
        """Test dangerous file paths."""
        dangerous_paths = [
            "../../../etc/passwd",
            "..\\..\\Windows\\System32",
            "/etc/shadow",
            "C:\\Windows\\System32\\config",
            "/proc/version",
        ]

        for path in dangerous_paths:
            with self.assertRaises(ValidationError):
                self.validator(path)

    def test_too_long_path(self):
        """Test path that exceeds maximum length."""
        long_path = "a" * 1001  # Default max is 1000
        with self.assertRaises(ValidationError):
            self.validator(long_path)

    def test_empty_path(self):
        """Test empty path (should be allowed)."""
        self.validator("")  # Should not raise


class GitHashValidatorTest(TestCase):
    """Tests for GitHashValidator."""

    def setUp(self):
        self.validator = GitHashValidator()

    def test_valid_hashes(self):
        """Test valid Git commit hashes."""
        valid_hashes = [
            "a1b2c3d",  # Short hash (7 chars)
            "a1b2c3d4e5f6",  # Medium hash (12 chars)
            "a1b2c3d4e5f67890abcdef1234567890abcdef12",  # Full hash (40 chars)
            "ABC123DEF456",  # Uppercase
        ]

        for hash_value in valid_hashes:
            try:
                self.validator(hash_value)
            except ValidationError:
                self.fail(f"Valid hash {hash_value} raised ValidationError")

    def test_invalid_hashes(self):
        """Test invalid Git commit hashes."""
        invalid_hashes = [
            "abc123",  # Too short (6 chars)
            "a1b2c3d4e5f67890abcdef1234567890abcdef123",  # Too long (41 chars)
            "g1h2i3j4k5l6",  # Invalid characters
            "abc-123-def",  # Contains dashes
            "",  # Empty (but should be allowed in validator)
        ]

        for hash_value in invalid_hashes[:-1]:  # Skip empty string
            with self.assertRaises(ValidationError):
                self.validator(hash_value)

        # Empty string should not raise
        self.validator("")


class GitBranchValidatorTest(TestCase):
    """Tests for GitBranchValidator."""

    def setUp(self):
        self.validator = GitBranchValidator()

    def test_valid_branches(self):
        """Test valid Git branch names."""
        valid_branches = ["main", "develop", "feature/new-feature", "bugfix/fix-123", "release/v1.2.3"]

        for branch in valid_branches:
            try:
                self.validator(branch)
            except ValidationError:
                self.fail(f"Valid branch {branch} raised ValidationError")

    def test_invalid_branches(self):
        """Test invalid Git branch names."""
        invalid_branches = [
            "/main",  # Starts with /
            "main/",  # Ends with /
            "main//develop",  # Double slashes
            "main..develop",  # Contains ..
            "main branch",  # Contains space
            "main~1",  # Contains ~
            "-main",  # Starts with -
            "main.",  # Ends with .
            "a" * 256,  # Too long
        ]

        for branch in invalid_branches:
            with self.assertRaises(ValidationError):
                self.validator(branch)


class IDENameValidatorTest(TestCase):
    """Tests for IDENameValidator."""

    def setUp(self):
        self.validator = IDENameValidator()

    def test_known_ides(self):
        """Test known IDE names."""
        known_ides = ["VSCode", "Visual Studio Code", "IntelliJ IDEA", "PyCharm", "Vim"]

        for ide in known_ides:
            try:
                self.validator(ide)
            except ValidationError:
                self.fail(f"Known IDE {ide} raised ValidationError")

    def test_unknown_ide(self):
        """Test unknown IDE (should not raise but may log)."""
        # Unknown IDE should not raise ValidationError
        self.validator("CustomIDE 2.0")

    def test_empty_ide(self):
        """Test empty IDE name."""
        with self.assertRaises(ValidationError):
            self.validator("")

    def test_too_long_ide(self):
        """Test IDE name that's too long."""
        long_ide = "a" * 101  # Max is 100
        with self.assertRaises(ValidationError):
            self.validator(long_ide)


class SessionMetadataValidatorTest(TestCase):
    """Tests for SessionMetadataValidator."""

    def setUp(self):
        self.validator = SessionMetadataValidator()

    def test_valid_metadata(self):
        """Test valid metadata structures."""
        valid_metadata = [
            {"theme": "dark"},
            {"settings": {"font_size": 14, "tab_size": 4}},
            {"plugins": ["plugin1", "plugin2"]},
            {"config": {"nested": {"deep": "value"}}},
        ]

        for metadata in valid_metadata:
            try:
                self.validator(metadata)
            except ValidationError:
                self.fail(f"Valid metadata {metadata} raised ValidationError")

    def test_invalid_metadata(self):
        """Test invalid metadata structures."""
        # Too many keys
        too_many_keys = {f"key_{i}": f"value_{i}" for i in range(51)}
        with self.assertRaises(ValidationError):
            self.validator(too_many_keys)

        # Too deeply nested
        deep_nested = {"a": {"b": {"c": {"d": "too deep"}}}}
        with self.assertRaises(ValidationError):
            self.validator(deep_nested)

        # Value too long
        long_value = {"key": "a" * 1001}  # Max is 1000
        with self.assertRaises(ValidationError):
            self.validator(long_value)

    def test_empty_metadata(self):
        """Test empty metadata (should be allowed)."""
        self.validator({})  # Should not raise


class NumericValidatorsTest(TestCase):
    """Tests for numeric validators."""

    def test_positive_integer_validator(self):
        """Test positive integer validator."""
        # Valid values
        validate_positive_integer(0)
        validate_positive_integer(100)
        validate_positive_integer(None)  # None should be allowed

        # Invalid values
        with self.assertRaises(ValidationError):
            validate_positive_integer(-1)

        with self.assertRaises(ValidationError):
            validate_positive_integer(-100)

    def test_reasonable_line_count_validator(self):
        """Test reasonable line count validator."""
        # Valid values
        validate_reasonable_line_count(0)
        validate_reasonable_line_count(10000)
        validate_reasonable_line_count(1000000)  # Exactly at limit
        validate_reasonable_line_count(None)  # None should be allowed

        # Invalid values
        with self.assertRaises(ValidationError):
            validate_reasonable_line_count(1000001)  # Over limit

    def test_complexity_score_validator(self):
        """Test complexity score validator."""
        # Valid values
        validate_complexity_score(0)
        validate_complexity_score(15.5)
        validate_complexity_score(1000)  # At upper limit
        validate_complexity_score(None)  # None should be allowed

        # Invalid values
        with self.assertRaises(ValidationError):
            validate_complexity_score(-1)  # Below minimum

        with self.assertRaises(ValidationError):
            validate_complexity_score(1001)  # Above maximum


class ActivityTypeValidatorTest(TestCase):
    """Tests for ActivityTypeValidator."""

    def test_valid_activity_types(self):
        """Test valid activity types."""
        from ..models import ActivityLog

        validator = ActivityTypeValidator()

        valid_types = [choice[0] for choice in ActivityLog.ACTIVITY_TYPE_CHOICES]

        for activity_type in valid_types:
            try:
                validator(activity_type)
            except ValidationError:
                self.fail(f"Valid activity type {activity_type} raised ValidationError")

    def test_invalid_activity_type(self):
        """Test invalid activity type."""
        validator = ActivityTypeValidator()

        with self.assertRaises(ValidationError):
            validator("invalid_activity_type")

    def test_window_focus_activity_type(self):
        """Test window_focus activity type is valid."""
        validator = ActivityTypeValidator()

        try:
            validator("window_focus")
        except ValidationError:
            self.fail("window_focus should be a valid activity type")


class GitEventTypeValidatorTest(TestCase):
    """Tests for GitEventTypeValidator."""

    def test_valid_git_event_types(self):
        """Test valid Git event types."""
        from ..models import GitEvent

        validator = GitEventTypeValidator()

        valid_types = [choice[0] for choice in GitEvent.EVENT_TYPE_CHOICES]

        for event_type in valid_types:
            try:
                validator(event_type)
            except ValidationError:
                self.fail(f"Valid git event type {event_type} raised ValidationError")

    def test_invalid_git_event_type(self):
        """Test invalid Git event type."""
        validator = GitEventTypeValidator()

        with self.assertRaises(ValidationError):
            validator("invalid_git_event_type")
