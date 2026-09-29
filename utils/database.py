import os
import re

import psycopg2
from dotenv import load_dotenv
from psycopg2 import sql


def database_config_from_env():
    load_dotenv()
    required = ("host", "database", "user", "password")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise ValueError(
            f"Missing PostgreSQL environment variables: {', '.join(missing)}"
        )
    return {
        "host": os.environ["host"],
        "port": int(os.environ.get("port", "5432")),
        "database": os.environ["database"],
        "user": os.environ["user"],
        "password": os.environ["password"],
    }


class DatabaseUtil:
    def __init__(self, db_config, max_rows=1000, statement_timeout_ms=10000):
        if max_rows < 1:
            raise ValueError("max_rows must be a positive integer.")
        self.connection = psycopg2.connect(**db_config)
        self.max_rows = max_rows
        self.statement_timeout_ms = statement_timeout_ms

    @staticmethod
    def validate_read_query(query):
        if not isinstance(query, str) or not query.strip():
            raise ValueError("SQL query must not be empty.")
        query = query.strip()
        if query.endswith(";"):
            query = query[:-1].rstrip()
        if ";" in query:
            raise ValueError("Only one SQL statement is allowed.")
        if re.match(r"\s*(SELECT|WITH)\b", query, re.IGNORECASE) is None:
            raise ValueError("Only SELECT queries are allowed.")
        return query

    def schema_details(self, schema_name):
        connection = self.connection
        cursor = None
        details = [f"Database Schema: {schema_name}"]
        try:
            connection.set_session(readonly=True)
            cursor = connection.cursor()
            cursor.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = %s AND table_type = 'BASE TABLE' "
                "ORDER BY table_name",
                (schema_name,),
            )
            for (table_name,) in cursor.fetchall():
                details.append(f"\nTable: {table_name}")
                cursor.execute(
                    "SELECT column_name, data_type "
                    "FROM information_schema.columns "
                    "WHERE table_schema = %s AND table_name = %s "
                    "ORDER BY ordinal_position",
                    (schema_name, table_name),
                )
                for column_name, data_type in cursor.fetchall():
                    details.append(f"  Column: {column_name}, Data Type: {data_type}")

                sample_query = sql.SQL("SELECT * FROM {} LIMIT 5").format(
                    sql.Identifier(schema_name, table_name)
                )
                cursor.execute(sample_query)
                details.append("  Sample Data:")
                details.extend(f"    {row}" for row in cursor.fetchall())

            connection.commit()
            return "\n".join(details)
        except Exception:
            connection.rollback()
            raise
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()

    def execute_sql(self, query):
        connection = self.connection
        cursor = None
        try:
            query = self.validate_read_query(query)
            connection.set_session(readonly=True)
            cursor = connection.cursor()
            cursor.execute(
                "SELECT set_config('statement_timeout', %s, true)",
                (f"{self.statement_timeout_ms}ms",),
            )
            cursor.execute(query)
            if cursor.description is None:
                raise ValueError("SQL query did not return rows.")
            rows = cursor.fetchmany(self.max_rows + 1)
            truncated = len(rows) > self.max_rows
            rows = rows[:self.max_rows]
            connection.commit()
            result = str(rows)
            if truncated:
                result += f"\nResults truncated to {self.max_rows} rows."
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()

