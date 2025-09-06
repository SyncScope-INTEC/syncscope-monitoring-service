"""
Tests for db_utils module.
"""

from unittest.mock import MagicMock, Mock, patch

from django.db import DatabaseError
from django.test import TestCase

from apps.monitoring.db_utils import DatabaseManager


class DatabaseManagerTest(TestCase):
    """Tests for DatabaseManager class."""

    @patch("apps.monitoring.db_utils.connection")
    def test_test_connection_success(self, mock_connection):
        """Test successful database connection test."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        result = DatabaseManager.test_connection()

        self.assertTrue(result)
        mock_cursor.execute.assert_called_once_with("SELECT 1")
        mock_cursor.fetchone.assert_called_once()

    @patch("apps.monitoring.db_utils.connection")
    def test_test_connection_wrong_result(self, mock_connection):
        """Test database connection test with wrong result."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (2,)  # Wrong result
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        result = DatabaseManager.test_connection()

        self.assertFalse(result)

    @patch("apps.monitoring.db_utils.connection")
    def test_test_connection_database_error(self, mock_connection):
        """Test database connection test with database error."""
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = DatabaseError("Connection failed")
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        result = DatabaseManager.test_connection()

        self.assertFalse(result)

    @patch("apps.monitoring.db_utils.connection")
    def test_test_connection_general_exception(self, mock_connection):
        """Test database connection test with general exception."""
        mock_connection.cursor.side_effect = Exception("Unexpected error")

        result = DatabaseManager.test_connection()

        self.assertFalse(result)

    @patch("apps.monitoring.db_utils.connection")
    def test_test_connection_cursor_exception(self, mock_connection):
        """Test database connection test when cursor operations fail."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = Exception("Cursor error")
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        result = DatabaseManager.test_connection()

        self.assertFalse(result)

    @patch("apps.monitoring.db_utils.connection")
    def test_get_schema_info_success(self, mock_connection):
        """Test successful schema info retrieval."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("monitoring",), ("auth",), ("analytics",)]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        result = DatabaseManager.get_schema_info()

        self.assertEqual(result, ["monitoring", "auth", "analytics"])
        mock_cursor.execute.assert_called_once()
        expected_query = """
                    SELECT schema_name 
                    FROM information_schema.schemata 
                    WHERE schema_name IN ('monitoring', 'auth', 'management', 'analytics', 'alerts', 'audit')
                    ORDER BY schema_name
                """
        # Check that the query contains the expected parts
        actual_query = mock_cursor.execute.call_args[0][0]
        self.assertIn("SELECT schema_name", actual_query)
        self.assertIn("FROM information_schema.schemata", actual_query)
        self.assertIn("monitoring", actual_query)
        self.assertIn("ORDER BY schema_name", actual_query)

    @patch("apps.monitoring.db_utils.connection")
    def test_get_schema_info_empty_result(self, mock_connection):
        """Test schema info retrieval with empty result."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        result = DatabaseManager.get_schema_info()

        self.assertEqual(result, [])

    @patch("apps.monitoring.db_utils.connection")
    def test_get_schema_info_database_error(self, mock_connection):
        """Test schema info retrieval with database error."""
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = DatabaseError("Schema query failed")
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        result = DatabaseManager.get_schema_info()

        self.assertEqual(result, [])

    @patch("apps.monitoring.db_utils.connection")
    def test_get_schema_info_general_exception(self, mock_connection):
        """Test schema info retrieval with general exception."""
        mock_connection.cursor.side_effect = Exception("Unexpected error")

        result = DatabaseManager.get_schema_info()

        self.assertEqual(result, [])

    @patch("apps.monitoring.db_utils.connection")
    def test_get_schema_info_cursor_fetchall_exception(self, mock_connection):
        """Test schema info retrieval when fetchall fails."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.side_effect = Exception("Fetchall error")
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        result = DatabaseManager.get_schema_info()

        self.assertEqual(result, [])

    @patch("apps.monitoring.db_utils.connection")
    def test_check_monitoring_tables_success(self, mock_connection):
        """Test successful monitoring tables check."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("developer_sessions",), ("activity_logs",), ("code_metrics",), ("git_events",)]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        result = DatabaseManager.check_monitoring_tables()

        self.assertEqual(result, ["developer_sessions", "activity_logs", "code_metrics", "git_events"])
        mock_cursor.execute.assert_called_once()
        expected_query = """
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'monitoring'
                    ORDER BY table_name
                """
        # Check that the query contains the expected parts
        actual_query = mock_cursor.execute.call_args[0][0]
        self.assertIn("SELECT table_name", actual_query)
        self.assertIn("FROM information_schema.tables", actual_query)
        self.assertIn("table_schema = 'monitoring'", actual_query)
        self.assertIn("ORDER BY table_name", actual_query)

    @patch("apps.monitoring.db_utils.connection")
    def test_check_monitoring_tables_empty_result(self, mock_connection):
        """Test monitoring tables check with empty result."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        result = DatabaseManager.check_monitoring_tables()

        self.assertEqual(result, [])

    @patch("apps.monitoring.db_utils.connection")
    def test_check_monitoring_tables_database_error(self, mock_connection):
        """Test monitoring tables check with database error."""
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = DatabaseError("Table query failed")
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        result = DatabaseManager.check_monitoring_tables()

        self.assertEqual(result, [])

    @patch("apps.monitoring.db_utils.connection")
    def test_check_monitoring_tables_general_exception(self, mock_connection):
        """Test monitoring tables check with general exception."""
        mock_connection.cursor.side_effect = Exception("Unexpected error")

        result = DatabaseManager.check_monitoring_tables()

        self.assertEqual(result, [])

    @patch("apps.monitoring.db_utils.connection")
    def test_check_monitoring_tables_cursor_fetchall_exception(self, mock_connection):
        """Test monitoring tables check when fetchall fails."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.side_effect = Exception("Fetchall error")
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        result = DatabaseManager.check_monitoring_tables()

        self.assertEqual(result, [])

    def test_static_methods(self):
        """Test that all methods are static methods."""
        # Verify that methods can be called on the class without instantiation
        with patch("apps.monitoring.db_utils.connection") as mock_connection:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = (1,)
            mock_cursor.fetchall.return_value = []
            mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

            # Should be able to call without instantiation
            DatabaseManager.test_connection()
            DatabaseManager.get_schema_info()
            DatabaseManager.check_monitoring_tables()

            # Verify we don't need to create an instance
            self.assertTrue(hasattr(DatabaseManager, "test_connection"))
            self.assertTrue(hasattr(DatabaseManager, "get_schema_info"))
            self.assertTrue(hasattr(DatabaseManager, "check_monitoring_tables"))

    @patch("apps.monitoring.db_utils.connection")
    def test_context_manager_behavior(self, mock_connection):
        """Test that cursor context manager is used correctly."""
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        # Test context manager setup
        DatabaseManager.test_connection()

        # Verify cursor was used as context manager
        mock_connection.cursor.assert_called()
        mock_cursor.__enter__.assert_called()
        mock_cursor.__exit__.assert_called()

    @patch("apps.monitoring.db_utils.logger")
    @patch("apps.monitoring.db_utils.connection")
    def test_logging_on_errors(self, mock_connection, mock_logger):
        """Test that errors are properly logged."""
        mock_connection.cursor.side_effect = Exception("Test error")

        DatabaseManager.test_connection()
        DatabaseManager.get_schema_info()
        DatabaseManager.check_monitoring_tables()

        # Verify logging was called for each method
        self.assertEqual(mock_logger.error.call_count, 3)

        # Check log messages contain expected content
        log_calls = mock_logger.error.call_args_list
        self.assertIn("Database connection failed", str(log_calls[0]))
        self.assertIn("Failed to get schema info", str(log_calls[1]))
        self.assertIn("Failed to check monitoring tables", str(log_calls[2]))
