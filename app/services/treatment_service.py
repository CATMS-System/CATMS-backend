"""
Treatment Service.

Provides database operations and business logic for treatments.
Service functions receive a PyMySQL connection (`pymysql.Connection`) as a parameter.
"""

from typing import Any, Dict, List
import pymysql
import pymysql.cursors


def get_categories(conn: pymysql.Connection) -> List[Dict[str, Any]]:
    """
    Retrieves all treatment categories ordered by Category_Name.
    Uses raw SQL with a DictCursor.
    """
    with conn.cursor(pymysql.cursors.DictCursor) as cursor:
        query = """
            SELECT Category_ID, Category_Name, Description
            FROM Treatment_Category
            ORDER BY Category_Name ASC
        """
        cursor.execute(query)
        return cursor.fetchall()
