"""
Management command to generate test data for development.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.monitoring.models import DeveloperSession, ActivityLog, CodeMetrics, GitEvent
from config.database_retry import database_retry
from datetime import timedelta
import random
import uuid


class Command(BaseCommand):
    help = 'Generate test data for development and testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--users',
            type=int,
            default=5,
            help='Number of users to generate data for (default: 5)'
        )
        parser.add_argument(
            '--sessions',
            type=int,
            default=20,
            help='Number of sessions per user (default: 20)'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Generate data for the last N days (default: 30)'
        )
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Clean existing test data before generating new data'
        )

    @database_retry(max_retries=3)
    def handle(self, *args, **options):
        users_count = options['users']
        sessions_per_user = options['sessions']
        days_back = options['days']
        clean = options['clean']
        
        if clean:
            self.stdout.write('Cleaning existing test data...')
            DeveloperSession.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('✓ Cleaned existing data'))
        
        self.stdout.write(f'Generating test data for {users_count} users...')
        
        # IDE choices
        ides = [
            ('VSCode', '1.85.0'),
            ('PyCharm', '2023.3'),
            ('IntelliJ IDEA', '2023.3'),
            ('Sublime Text', '4.0'),
            ('Vim', '9.0'),
            ('WebStorm', '2023.3'),
        ]
        
        # File extensions and activity types
        file_extensions = ['py', 'js', 'ts', 'java', 'cpp', 'go', 'rs', 'php']
        activity_types = ['file_open', 'file_edit', 'file_save', 'file_close', 'debug_start', 'test_run']
        git_events = ['commit', 'push', 'pull', 'merge', 'checkout']
        
        total_created = {
            'sessions': 0,
            'activities': 0,
            'metrics': 0,
            'git_events': 0
        }
        
        for user_id in range(1, users_count + 1):
            self.stdout.write(f'  User {user_id}: ', ending='')
            
            user_sessions = 0
            user_activities = 0
            user_metrics = 0
            user_git_events = 0
            
            for session_num in range(sessions_per_user):
                # Random session timing within the last N days
                start_time = timezone.now() - timedelta(
                    days=random.randint(0, days_back),
                    hours=random.randint(0, 23),
                    minutes=random.randint(0, 59)
                )
                
                # Session duration between 10 minutes and 8 hours
                duration_minutes = random.randint(10, 480)
                end_time = start_time + timedelta(minutes=duration_minutes)
                
                # Choose random IDE
                ide_name, ide_version = random.choice(ides)
                
                # Create session
                session = DeveloperSession.objects.create(
                    user_id=user_id,
                    session_start=start_time,
                    session_end=end_time,
                    session_duration_minutes=duration_minutes,
                    ide_name=ide_name,
                    ide_version=ide_version,
                    project_path=f'/home/user{user_id}/project{session_num + 1}',
                    git_repository_url=f'https://github.com/user{user_id}/repo{session_num + 1}.git',
                    git_branch=random.choice(['main', 'develop', 'feature/new-feature']),
                    git_commit_hash=f'{random.randint(100000, 999999):06x}',
                    operating_system=random.choice(['Linux', 'macOS', 'Windows']),
                    session_metadata={
                        'theme': random.choice(['dark', 'light']),
                        'font_size': random.choice([12, 14, 16]),
                    }
                )
                user_sessions += 1
                
                # Generate activities for this session
                num_activities = random.randint(5, 50)
                for _ in range(num_activities):
                    activity_time = start_time + timedelta(
                        minutes=random.randint(0, duration_minutes)
                    )
                    
                    file_ext = random.choice(file_extensions)
                    ActivityLog.objects.create(
                        session=session,
                        activity_type=random.choice(activity_types),
                        timestamp=activity_time,
                        file_path=f'/project/src/file{random.randint(1, 100)}.{file_ext}',
                        activity_metadata={
                            'lines_changed': random.randint(1, 50),
                        }
                    )
                    user_activities += 1
                
                # Generate code metrics
                num_metrics = random.randint(1, 10)
                for _ in range(num_metrics):
                    file_ext = random.choice(file_extensions)
                    CodeMetrics.objects.create(
                        session=session,
                        file_path=f'/project/src/metrics_file{random.randint(1, 50)}.{file_ext}',
                        lines_of_code=random.randint(10, 1000),
                        lines_added=random.randint(0, 100),
                        lines_deleted=random.randint(0, 50),
                        lines_modified=random.randint(0, 30),
                        complexity_score=round(random.uniform(1, 50), 2),
                        function_count=random.randint(1, 20),
                        class_count=random.randint(0, 5),
                        comment_lines=random.randint(5, 100),
                        blank_lines=random.randint(10, 200),
                        calculated_at=activity_time
                    )
                    user_metrics += 1
                
                # Generate git events
                num_git_events = random.randint(0, 5)
                for _ in range(num_git_events):
                    event_time = start_time + timedelta(
                        minutes=random.randint(0, duration_minutes)
                    )
                    
                    GitEvent.objects.create(
                        session=session,
                        event_type=random.choice(git_events),
                        timestamp=event_time,
                        commit_hash=f'{random.randint(100000, 999999):06x}abc{random.randint(100, 999)}',
                        commit_message=f'Commit message {random.randint(1, 1000)}',
                        branch_name=random.choice(['main', 'develop', 'feature/test']),
                        insertions=random.randint(1, 100),
                        deletions=random.randint(0, 50),
                        author_name=f'User {user_id}',
                        author_email=f'user{user_id}@example.com'
                    )
                    user_git_events += 1
            
            total_created['sessions'] += user_sessions
            total_created['activities'] += user_activities
            total_created['metrics'] += user_metrics
            total_created['git_events'] += user_git_events
            
            self.stdout.write(
                f'{user_sessions}s, {user_activities}a, {user_metrics}m, {user_git_events}g'
            )
        
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write(self.style.SUCCESS('Test data generation complete!'))
        self.stdout.write(f'Created:')
        self.stdout.write(f'  - {total_created["sessions"]} sessions')
        self.stdout.write(f'  - {total_created["activities"]} activities')
        self.stdout.write(f'  - {total_created["metrics"]} code metrics')
        self.stdout.write(f'  - {total_created["git_events"]} git events')
        self.stdout.write('=' * 50)