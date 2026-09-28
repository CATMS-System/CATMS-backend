from typing import Generator
import pymysql
from app.db.connection import get_db

# Re-export get_db so all routers import dependencies uniformly from app.api.deps
__all__ = ["get_db"]
