"""
Management command to check service health.
"""

from django.core.management.base import BaseCommand
from apps.monitoring.mixins import CacheHealthCheck
from config.database_retry import DatabaseHealthCheck
from apps.monitoring.models import DeveloperSession, ActivityLog, CodeMetrics, GitEvent
from django.db import connection
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Perform comprehensive health check of the monitoring service'

    def add_arguments(self, parser):
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Show detailed health information'
        )
        parser.add_argument(
            '--exit-code',
            action='store_true',
            help='Exit with non-zero code if unhealthy'
        )

    def handle(self, *args, **options):
        detailed = options['detailed']
        exit_code = options['exit_code']
        
        self.stdout.write('=' * 60)
        self.stdout.write(self.style.HTTP_INFO('SyncScope Monitoring Service Health Check'))
        self.stdout.write('=' * 60)
        
        overall_healthy = True
        
        # Database health
        self.stdout.write('\n1. Database Health:')
        try:
            db_healthy = DatabaseHealthCheck.is_healthy(use_cache=False)
            if db_healthy:
                self.stdout.write(self.style.SUCCESS('  ✓ Database: HEALTHY'))
                
                if detailed:
                    # Schema information
                    schemas = DatabaseHealthCheck.get_schema_info()
                    self.stdout.write(f'    Available schemas: {", ".join(schemas)}')
                    
                    # Connection info
                    with connection.cursor() as cursor:
                        cursor.execute('SELECT version()')
                        db_version = cursor.fetchone()[0]
                        self.stdout.write(f'    Database: {db_version.split()[0]} {db_version.split()[1]}')
            else:
                self.stdout.write(self.style.ERROR('  ✗ Database: UNHEALTHY'))
                overall_healthy = False
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ✗ Database: ERROR - {e}'))
            overall_healthy = False
        
        # Cache/Redis health
        self.stdout.write('\n2. Redis/Cache Health:')
        try:
            cache_healthy = CacheHealthCheck.is_healthy()
            if cache_healthy:
                self.stdout.write(self.style.SUCCESS('  ✓ Redis: HEALTHY'))
            else:
                self.stdout.write(self.style.ERROR('  ✗ Redis: UNHEALTHY'))
                overall_healthy = False
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ✗ Redis: ERROR - {e}'))
            overall_healthy = False
        
        # Model health (basic queries)
        self.stdout.write('\n3. Model Health:')
        model_checks = [
            ('DeveloperSession', DeveloperSession),
            ('ActivityLog', ActivityLog),
            ('CodeMetrics', CodeMetrics),
            ('GitEvent', GitEvent),
        ]
        
        for model_name, model_class in model_checks:
            try:
                count = model_class.objects.count()
                self.stdout.write(self.style.SUCCESS(f'  ✓ {model_name}: {count} records'))
                
                if detailed and count > 0:
                    # Latest record
                    latest = model_class.objects.latest('created_at')
                    self.stdout.write(f'    Latest record: {latest.created_at}')
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✗ {model_name}: ERROR - {e}'))
                overall_healthy = False
        
        # System information (if detailed)
        if detailed:
            self.stdout.write('\n4. System Information:')
            try:
                import psutil
                import os
                
                self.stdout.write(f'  Process ID: {os.getpid()}')
                self.stdout.write(f'  Memory usage: {psutil.virtual_memory().percent}%')
                self.stdout.write(f'  CPU usage: {psutil.cpu_percent()}%')
                self.stdout.write(f'  Disk usage: {psutil.disk_usage("/").percent}%')
                
            except ImportError:
                self.stdout.write('  System metrics unavailable (psutil not installed)')
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  System metrics error: {e}'))
        
        # Configuration check
        self.stdout.write('\n5. Configuration:')
        from django.conf import settings
        
        config_checks = [
            ('DEBUG', getattr(settings, 'DEBUG', None)),
            ('DATABASE_URL', bool(getattr(settings, 'DATABASES', {}).get('default', {}).get('NAME'))),
            ('REDIS_URL', bool(getattr(settings, 'CACHES', {}).get('default', {}).get('LOCATION'))),
            ('SECRET_KEY', bool(getattr(settings, 'SECRET_KEY', ''))),
        ]
        
        for check_name, check_value in config_checks:
            if check_value:
                self.stdout.write(self.style.SUCCESS(f'  ✓ {check_name}: Configured'))
            else:
                self.stdout.write(self.style.ERROR(f'  ✗ {check_name}: Missing/Invalid'))
                if check_name in ['DATABASE_URL', 'SECRET_KEY']:
                    overall_healthy = False
        
        # Final status
        self.stdout.write('\n' + '=' * 60)
        if overall_healthy:
            self.stdout.write(self.style.SUCCESS('OVERALL STATUS: HEALTHY ✓'))
            self.stdout.write('Service is ready to accept traffic')
            exit_status = 0
        else:
            self.stdout.write(self.style.ERROR('OVERALL STATUS: UNHEALTHY ✗'))
            self.stdout.write('Service has critical issues')
            exit_status = 1
        
        self.stdout.write('=' * 60)
        
        if exit_code and exit_status != 0:
            raise SystemExit(exit_status)