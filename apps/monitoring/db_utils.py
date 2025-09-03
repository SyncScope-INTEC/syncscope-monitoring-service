"""
Database utilities for monitoring service.
"""

import logging

from django.conf import settings
from django.db import connection

logger = logging.getLogger(__name__)


class DatabaseManager:
    @staticmethod
    def test_connection():
        """Test database connection."""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                return result[0] == 1
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False

    @staticmethod
    def get_schema_info():
        """Get information about current database schemas."""
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT schema_name 
                    FROM information_schema.schemata 
                    WHERE schema_name IN ('monitoring', 'auth', 'management', 'analytics', 'alerts', 'audit')
                    ORDER BY schema_name
                """
                )
                schemas = [row[0] for row in cursor.fetchall()]
                return schemas
        except Exception as e:
            logger.error(f"Failed to get schema info: {e}")
            return []

    @staticmethod
    def check_monitoring_tables():
        """Check if monitoring schema tables exist."""
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'monitoring'
                    ORDER BY table_name
                """
                )
                tables = [row[0] for row in cursor.fetchall()]
                return tables
        except Exception as e:
            logger.error(f"Failed to check monitoring tables: {e}")
            return []
