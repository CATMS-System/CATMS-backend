import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.connection import get_db_connection


def test_database_connectivity_option_c():
    """Verifies database connectivity using Option C (Plain PyMySQL with DictCursor)."""
    conn = get_db_connection()
    try:
        # Option C: Plain PyMySQL manual SQL execution
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 AS status, VERSION() AS db_version")
            result = cursor.fetchone()
            assert result is not None
            assert result["status"] == 1
            print("Test Passed: Option C plain PyMySQL query executed successfully!")
            print(f"Database response: {result}")
    finally:
        conn.close()


if __name__ == "__main__":
    test_database_connectivity_option_c()
