from typing import Generator
from app.db.session import get_db

# Re-export get_db so routers can import dependencies from app.api.deps
__all__ = ["get_db"]
