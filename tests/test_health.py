import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from app.db.session import SessionLocal


def test_database_connectivity_option_b():
    """Verifies database connectivity using Option B (Manual SQL with SQLAlchemy Session)."""
    db = SessionLocal()
    try:
        # Option B: Manual SQL execution via text()
        result = db.execute(text("SELECT 1 AS status")).mappings().first()
        assert result is not None
        assert result["status"] == 1
        print("Test Passed: Option B manual SQL query executed successfully!")
    finally:
        db.close()


if __name__ == "__main__":
    test_database_connectivity_option_b()
