"""
Database connection management for Option C (Plain PyMySQL).
Provides get_db() dependency yielding a raw PyMySQL connection with DictCursor.
"""

import certifi
import pymysql
import pymysql.cursors
from typing import Generator
from app.core.config import settings


def get_db_connection() -> pymysql.Connection:
    """Creates and returns a raw PyMySQL connection to the database."""
    ssl_config = None
    if settings.DB_USE_SSL:
        ssl_config = {"ca": certifi.where()}

    return pymysql.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
        ssl=ssl_config,
        autocommit=False,
        connect_timeout=10
    )


def get_db() -> Generator[pymysql.Connection, None, None]:
    """
    FastAPI dependency yielding a clean PyMySQL database connection per request.
    Automatically closes the connection upon request completion.
    """
    connection = get_db_connection()
    try:
        yield connection
    finally:
        connection.close()
