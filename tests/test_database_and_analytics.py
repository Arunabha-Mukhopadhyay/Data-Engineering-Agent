import unittest
from unittest.mock import Mock

from utils.analytics import REPORT_QUERIES
from utils.database import DatabaseUtil


class DatabaseSafetyTests(unittest.TestCase):
    def test_query_guard_accepts_reads_and_rejects_mutations(self):
        DatabaseUtil.validate_read_query("SELECT 1")
        DatabaseUtil.validate_read_query("WITH sample AS (SELECT 1) SELECT * FROM sample")

        for query in (
            "DELETE FROM rides",
            "DROP TABLE rides",
            "SELECT 1; DELETE FROM rides",
        ):
            with self.subTest(query=query):
                with self.assertRaises(ValueError):
                    DatabaseUtil.validate_read_query(query)

    def test_execute_sql_uses_readonly_transaction_and_caps_rows(self):
        database = DatabaseUtil.__new__(DatabaseUtil)
        database.connection = Mock()
        database.max_rows = 2
        database.statement_timeout_ms = 5000
        cursor = database.connection.cursor.return_value
        cursor.description = ("value",)
        cursor.fetchmany.return_value = [(1,), (2,), (3,)]

        result = database.execute_sql("SELECT value FROM test")

        database.connection.set_session.assert_called_once_with(readonly=True)
        cursor.fetchmany.assert_called_once_with(3)
        self.assertIn("truncated to 2 rows", result)
        database.connection.close.assert_called_once()

    def test_analytics_queries_are_read_only(self):
        self.assertEqual(len(REPORT_QUERIES), 4)
        for name, query in REPORT_QUERIES.items():
            with self.subTest(report=name):
                DatabaseUtil.validate_read_query(query)


if __name__ == "__main__":
    unittest.main()