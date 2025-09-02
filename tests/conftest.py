"""
Pytest fixtures and test utilities for monitoring service.
"""

import pytest
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from datetime import timedelta
from unittest.mock import Mock, MagicMock
import uuid

from apps.monitoring.models import DeveloperSession, ActivityLog, CodeMetrics, GitEvent
from apps.monitoring.authentication import MonitoringUser


@pytest.fixture
def api_client():
    """API client for testing."""
    return APIClient()


@pytest.fixture
def mock_user():
    """Mock user for authentication."""
    return MonitoringUser({
        'user_id': 1,
        'email': 'test@example.com',
        'username': 'testuser',
        'is_staff': False,
        'is_superuser': False
    })


@pytest.fixture
def admin_user():
    """Mock admin user for authentication."""
    return MonitoringUser({
        'user_id': 2,
        'email': 'admin@example.com',
        'username': 'adminuser',
        'is_staff': True,
        'is_superuser': True
    })


@pytest.fixture
def authenticated_client(api_client, mock_user):
    """API client with authentication."""
    api_client.force_authenticate(user=mock_user)
    return api_client


@pytest.fixture
def admin_client(api_client, admin_user):
    """API client with admin authentication."""
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def developer_session(db):
    """Create a test developer session."""
    return DeveloperSession.objects.create(
        user_id=1,
        ide_name='VSCode',
        ide_version='1.85.0',
        project_path='/home/user/test-project',
        git_repository_url='https://github.com/user/test-repo.git',
        git_branch='main',
        git_commit_hash='abc123def456',
        operating_system='Linux',
        session_metadata={'theme': 'dark', 'font_size': 14}
    )


@pytest.fixture
def completed_session(db):
    """Create a completed test session."""
    start_time = timezone.now() - timedelta(hours=2)
    end_time = start_time + timedelta(hours=1)
    
    return DeveloperSession.objects.create(
        user_id=1,
        session_start=start_time,
        session_end=end_time,
        session_duration_minutes=60,
        ide_name='PyCharm',
        ide_version='2023.3',
        project_path='/home/user/completed-project',
        operating_system='macOS'
    )


@pytest.fixture
def expired_session(db):
    """Create an expired test session."""
    start_time = timezone.now() - timedelta(hours=25)  # Older than 24 hours
    
    return DeveloperSession.objects.create(
        user_id=1,
        session_start=start_time,
        ide_name='Vim',
        operating_system='Linux'
    )


@pytest.fixture
def activity_log(developer_session):
    """Create a test activity log."""
    return ActivityLog.objects.create(
        session=developer_session,
        activity_type='file_open',
        file_path='/project/src/test.py',
        activity_metadata={'size': 1024, 'encoding': 'utf-8'}
    )


@pytest.fixture
def code_metrics(developer_session):
    """Create test code metrics."""
    return CodeMetrics.objects.create(
        session=developer_session,
        file_path='/project/src/main.py',
        lines_of_code=150,
        lines_added=20,
        lines_deleted=5,
        lines_modified=10,
        complexity_score=15.5,
        function_count=8,
        class_count=2,
        comment_lines=25,
        blank_lines=35
    )


@pytest.fixture
def git_event(developer_session):
    """Create a test git event."""
    return GitEvent.objects.create(
        session=developer_session,
        event_type='commit',
        commit_hash='abc123def456789',
        commit_message='Test commit message',
        branch_name='main',
        insertions=25,
        deletions=8,
        author_name='Test User',
        author_email='test@example.com'
    )


@pytest.fixture
def multiple_sessions(db):
    """Create multiple test sessions for different users."""
    sessions = []
    
    # User 1: 3 sessions
    for i in range(3):
        start_time = timezone.now() - timedelta(days=i, hours=2)
        end_time = start_time + timedelta(hours=1) if i > 0 else None  # First session is active
        duration = 60 if end_time else None
        
        session = DeveloperSession.objects.create(
            user_id=1,
            session_start=start_time,
            session_end=end_time,
            session_duration_minutes=duration,
            ide_name=f'IDE{i + 1}',
            operating_system='Linux'
        )
        sessions.append(session)
    
    # User 2: 2 sessions
    for i in range(2):
        start_time = timezone.now() - timedelta(days=i + 3, hours=1)
        session = DeveloperSession.objects.create(
            user_id=2,
            session_start=start_time,
            session_end=start_time + timedelta(minutes=45),
            session_duration_minutes=45,
            ide_name='VSCode',
            operating_system='Windows'
        )
        sessions.append(session)
    
    return sessions


@pytest.fixture
def bulk_activities_data(developer_session):
    """Sample data for bulk activities endpoint."""
    return {
        'session_id': str(developer_session.session_id),
        'activities': [
            {
                'activity_type': 'file_open',
                'file_path': '/project/src/file1.py',
                'activity_metadata': {'size': 1024}
            },
            {
                'activity_type': 'file_edit',
                'file_path': '/project/src/file2.js',
                'activity_metadata': {'changes': 5}
            },
            {
                'activity_type': 'file_save',
                'file_path': '/project/src/file3.ts',
                'activity_metadata': {'auto_save': False}
            }
        ]
    }


@pytest.fixture
def code_metrics_data(developer_session):
    """Sample data for code metrics endpoint."""
    return {
        'session': str(developer_session.session_id),
        'file_path': '/project/src/metrics_test.py',
        'lines_of_code': 200,
        'lines_added': 15,
        'lines_deleted': 3,
        'lines_modified': 7,
        'complexity_score': 18.2,
        'function_count': 12,
        'class_count': 3,
        'comment_lines': 40,
        'blank_lines': 50
    }


@pytest.fixture
def git_event_data(developer_session):
    """Sample data for git event endpoint."""
    return {
        'session': str(developer_session.session_id),
        'event_type': 'push',
        'commit_hash': '123abc456def789',
        'commit_message': 'Test push commit',
        'branch_name': 'feature/test',
        'remote_name': 'origin',
        'files_changed': 3,
        'insertions': 45,
        'deletions': 12,
        'author_name': 'Test Developer',
        'author_email': 'dev@example.com'
    }


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing."""
    mock_client = MagicMock()
    mock_client.set_session_data.return_value = True
    mock_client.get_session_data.return_value = None
    mock_client.delete_session_data.return_value = True
    mock_client.set_metrics_cache.return_value = True
    mock_client.get_metrics_cache.return_value = None
    return mock_client


@pytest.fixture
def mock_database_healthy():
    """Mock database health check as healthy."""
    with pytest.mock.patch('config.database_retry.DatabaseHealthCheck.is_healthy') as mock:
        mock.return_value = True
        yield mock


@pytest.fixture
def mock_database_unhealthy():
    """Mock database health check as unhealthy."""
    with pytest.mock.patch('config.database_retry.DatabaseHealthCheck.is_healthy') as mock:
        mock.return_value = False
        yield mock


@pytest.fixture
def mock_cache_healthy():
    """Mock cache health check as healthy."""
    with pytest.mock.patch('apps.monitoring.mixins.CacheHealthCheck.is_healthy') as mock:
        mock.return_value = True
        yield mock


@pytest.fixture
def mock_cache_unhealthy():
    """Mock cache health check as unhealthy."""
    with pytest.mock.patch('apps.monitoring.mixins.CacheHealthCheck.is_healthy') as mock:
        mock.return_value = False
        yield mock


class MonitoringTestCase(TestCase):
    """Base test case class with common utilities."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.mock_user = MonitoringUser({
            'user_id': 1,
            'email': 'test@example.com',
            'username': 'testuser'
        })
        self.client.force_authenticate(user=self.mock_user)
    
    def create_test_session(self, user_id=1, active=True):
        """Helper method to create a test session."""
        start_time = timezone.now() - timedelta(minutes=30)
        end_time = None if active else timezone.now() - timedelta(minutes=10)
        duration = None if active else 20
        
        return DeveloperSession.objects.create(
            user_id=user_id,
            session_start=start_time,
            session_end=end_time,
            session_duration_minutes=duration,
            ide_name='VSCode',
            operating_system='Linux'
        )
    
    def create_test_activity(self, session, activity_type='file_open'):
        """Helper method to create a test activity."""
        return ActivityLog.objects.create(
            session=session,
            activity_type=activity_type,
            file_path=f'/test/{activity_type}_file.py'
        )
    
    def create_test_metrics(self, session):
        """Helper method to create test code metrics."""
        return CodeMetrics.objects.create(
            session=session,
            file_path='/test/metrics_file.py',
            lines_of_code=100,
            lines_added=10,
            lines_deleted=2,
            lines_modified=5
        )
    
    def create_test_git_event(self, session, event_type='commit'):
        """Helper method to create a test git event."""
        return GitEvent.objects.create(
            session=session,
            event_type=event_type,
            commit_hash=f'test{event_type}hash123',
            commit_message=f'Test {event_type} message',
            branch_name='test-branch'
        )
    
    def assert_response_structure(self, response, expected_fields):
        """Assert that response has expected structure."""
        self.assertIsInstance(response.data, dict)
        for field in expected_fields:
            self.assertIn(field, response.data, f"Missing field: {field}")
    
    def assert_error_response(self, response, expected_error_code=None):
        """Assert that response is a properly formatted error."""
        self.assertIsInstance(response.data, dict)
        self.assertIn('error', response.data)
        self.assertIn('message', response.data)
        self.assertIn('status', response.data)
        self.assertEqual(response.data['status'], 'error')
        
        if expected_error_code:
            self.assertEqual(response.data['error'], expected_error_code)