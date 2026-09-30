"""
Treatment Service.

Provides database operations and business logic for treatments.
Service functions receive a PyMySQL connection (`pymysql.Connection`) as a parameter.
"""

from typing import Any, Dict, List, Optional
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


def get_catalogue(
    conn: pymysql.Connection,
    search: Optional[str] = None,
    category_id: Optional[int] = None,
    include_discontinued: bool = False
) -> List[Dict[str, Any]]:
    """
    Retrieves treatments joined with Treatment_Category.
    When include_discontinued is False (default), only returns Treatment_Status='Active'.
    When include_discontinued is True, returns all treatments regardless of status.
    Optionally filters by Category_ID and/or search term matching Treatment_Name or Service_Code.
    Ordered by Category_Name ASC, then Treatment_Name ASC.
    Uses raw SQL with a DictCursor.
    """
    query = """
        SELECT 
            t.Treatment_ID,
            t.Category_ID,
            tc.Category_Name,
            t.Service_Code,
            t.Treatment_Name,
            t.Description,
            t.Standard_Unit_Price,
            t.Treatment_Status
        FROM Treatment_Catalogue t
        JOIN Treatment_Category tc ON t.Category_ID = tc.Category_ID
        WHERE 1=1
    """
    params = []

    if not include_discontinued:
        query += " AND t.Treatment_Status = 'Active'"

    if category_id is not None:
        query += " AND t.Category_ID = %s"
        params.append(category_id)

    if search:
        query += " AND (t.Treatment_Name LIKE %s OR t.Service_Code LIKE %s)"
        search_pattern = f"%{search}%"
        params.extend([search_pattern, search_pattern])

    query += " ORDER BY tc.Category_Name ASC, t.Treatment_Name ASC"

    with conn.cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute(query, tuple(params))
        return cursor.fetchall()
