"""
Management command to set up test database with proper schema
"""

import os

import psycopg2
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Set up test database with monitoring schema"

    def handle(self, *args, **options):
        """Create monitoring schema in test database"""
        db_config = settings.DATABASES["default"]

        try:
            # Connect to the database
            conn = psycopg2.connect(
                host=db_config["HOST"],
                port=db_config["PORT"],
                user=db_config["USER"],
                password=db_config["PASSWORD"],
                database=db_config["NAME"],
            )

            conn.autocommit = True
            cursor = conn.cursor()

            # Create monitoring schema
            cursor.execute("CREATE SCHEMA IF NOT EXISTS monitoring;")
            self.stdout.write(self.style.SUCCESS("✓ Monitoring schema created successfully"))

            cursor.close()
            conn.close()

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error creating monitoring schema: {e}"))
            raise
