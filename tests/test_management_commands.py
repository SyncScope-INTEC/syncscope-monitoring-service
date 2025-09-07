"""
Tests for management commands.
"""

from io import StringIO
from unittest.mock import MagicMock, Mock, patch

import psycopg2
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from apps.monitoring.management.commands.setup_test_db import Command


class SetupTestDbCommandTest(TestCase):
    """Tests for setup_test_db management command."""

    def setUp(self):
        self.command = Command()
        self.out = StringIO()
        self.err = StringIO()

    @patch("apps.monitoring.management.commands.setup_test_db.psycopg2.connect")
    @override_settings(
        DATABASES={
            "default": {"HOST": "localhost", "PORT": "5432", "USER": "testuser", "PASSWORD": "testpass", "NAME": "testdb"}
        }
    )
    def test_setup_test_db_success(self, mock_connect):
        """Test successful database setup."""
        # Mock database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        # Run command
        self.command.stdout = self.out
        self.command.style = Mock()
        self.command.style.SUCCESS.return_value = "✓ Monitoring schema created successfully"

        self.command.handle()

        # Verify connection was made with correct parameters
        mock_connect.assert_called_once_with(
            host="localhost", port="5432", user="testuser", password="testpass", database="testdb"
        )

        # Verify autocommit was enabled
        self.assertTrue(mock_conn.autocommit)

        # Verify schema creation SQL was executed
        mock_cursor.execute.assert_called_once_with("CREATE SCHEMA IF NOT EXISTS monitoring;")

        # Verify connections were closed
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch("apps.monitoring.management.commands.setup_test_db.psycopg2.connect")
    @override_settings(
        DATABASES={
            "default": {"HOST": "localhost", "PORT": "5432", "USER": "testuser", "PASSWORD": "testpass", "NAME": "testdb"}
        }
    )
    def test_setup_test_db_connection_error(self, mock_connect):
        """Test handling of database connection errors."""
        # Mock connection failure
        mock_connect.side_effect = psycopg2.OperationalError("Connection failed")

        self.command.stdout = self.out
        self.command.style = Mock()
        self.command.style.ERROR.return_value = "Error creating monitoring schema: Connection failed"

        # Command should raise the exception after logging
        with self.assertRaises(psycopg2.OperationalError):
            self.command.handle()

    @patch("apps.monitoring.management.commands.setup_test_db.psycopg2.connect")
    @override_settings(
        DATABASES={
            "default": {"HOST": "localhost", "PORT": "5432", "USER": "testuser", "PASSWORD": "testpass", "NAME": "testdb"}
        }
    )
    def test_setup_test_db_execution_error(self, mock_connect):
        """Test handling of SQL execution errors."""
        # Mock successful connection but failed SQL execution
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = psycopg2.ProgrammingError("SQL execution failed")
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        self.command.stdout = self.out
        self.command.style = Mock()
        self.command.style.ERROR.return_value = "Error creating monitoring schema: SQL execution failed"

        # Command should raise the exception after logging
        with self.assertRaises(psycopg2.ProgrammingError):
            self.command.handle()

        # Note: Current implementation doesn't have proper cleanup in exception handler
        # This is a limitation of the current code - in a real implementation,
        # cleanup should happen in a finally block

    @patch("apps.monitoring.management.commands.setup_test_db.psycopg2.connect")
    @override_settings(
        DATABASES={
            "default": {
                "HOST": "custom-host",
                "PORT": "5433",
                "USER": "custom-user",
                "PASSWORD": "custom-pass",
                "NAME": "custom-db",
            }
        }
    )
    def test_setup_test_db_custom_settings(self, mock_connect):
        """Test command with custom database settings."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        self.command.stdout = self.out
        self.command.style = Mock()
        self.command.style.SUCCESS.return_value = "Success message"

        self.command.handle()

        # Verify connection used custom settings
        mock_connect.assert_called_once_with(
            host="custom-host", port="5433", user="custom-user", password="custom-pass", database="custom-db"
        )

    def test_command_help_text(self):
        """Test command help text is set correctly."""
        self.assertEqual(self.command.help, "Set up test database with monitoring schema")

    @patch("apps.monitoring.management.commands.setup_test_db.psycopg2.connect")
    def test_command_via_call_command(self, mock_connect):
        """Test running command via Django's call_command."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        out = StringIO()

        # This should not raise any errors
        call_command("setup_test_db", stdout=out)

        # Verify the command was executed
        mock_connect.assert_called_once()
        mock_cursor.execute.assert_called_once_with("CREATE SCHEMA IF NOT EXISTS monitoring;")

    @patch("apps.monitoring.management.commands.setup_test_db.psycopg2.connect")
    def test_autocommit_enabled(self, mock_connect):
        """Test that autocommit is properly enabled."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        self.command.stdout = self.out
        self.command.style = Mock()
        self.command.style.SUCCESS.return_value = "Success"

        self.command.handle()

        # Verify autocommit was set to True
        self.assertTrue(mock_conn.autocommit)

    @patch("apps.monitoring.management.commands.setup_test_db.psycopg2.connect")
    def test_schema_creation_sql(self, mock_connect):
        """Test the exact SQL executed for schema creation."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        self.command.stdout = self.out
        self.command.style = Mock()
        self.command.style.SUCCESS.return_value = "Success"

        self.command.handle()

        # Verify exact SQL command
        expected_sql = "CREATE SCHEMA IF NOT EXISTS monitoring;"
        mock_cursor.execute.assert_called_once_with(expected_sql)

    @patch("apps.monitoring.management.commands.setup_test_db.psycopg2.connect")
    def test_exception_during_cursor_creation(self, mock_connect):
        """Test handling of exception during cursor creation."""
        mock_conn = MagicMock()
        mock_conn.cursor.side_effect = Exception("Cursor creation failed")
        mock_connect.return_value = mock_conn

        self.command.stdout = self.out
        self.command.style = Mock()
        self.command.style.ERROR.return_value = "Error creating monitoring schema: Cursor creation failed"

        with self.assertRaises(Exception):
            self.command.handle()

        # Note: Current implementation doesn't clean up properly on cursor creation failure

    @patch("apps.monitoring.management.commands.setup_test_db.psycopg2.connect")
    @override_settings(
        DATABASES={
            "default": {
                "HOST": "",  # Empty host
                "PORT": "",  # Empty port
                "USER": "",  # Empty user
                "PASSWORD": "",  # Empty password
                "NAME": "",  # Empty name
            }
        }
    )
    def test_setup_test_db_empty_settings(self, mock_connect):
        """Test command with empty database settings."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        self.command.stdout = self.out
        self.command.style = Mock()
        self.command.style.SUCCESS.return_value = "Success"

        self.command.handle()

        # Should still attempt connection with empty values
        mock_connect.assert_called_once_with(host="", port="", user="", password="", database="")

    def test_command_inherits_from_base_command(self):
        """Test that command properly inherits from BaseCommand."""
        from django.core.management.base import BaseCommand

        self.assertIsInstance(self.command, BaseCommand)

    @patch("apps.monitoring.management.commands.setup_test_db.psycopg2.connect")
    def test_general_exception_handling(self, mock_connect):
        """Test handling of general exceptions."""
        # Mock a general exception (not psycopg2 specific)
        mock_connect.side_effect = ValueError("Unexpected error")

        self.command.stdout = self.out
        self.command.style = Mock()
        self.command.style.ERROR.return_value = "Error creating monitoring schema: Unexpected error"

        with self.assertRaises(ValueError):
            self.command.handle()
