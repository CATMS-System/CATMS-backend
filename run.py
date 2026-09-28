"""
Entry point to run the CATMS FastAPI backend service.
Runs Uvicorn on host 0.0.0.0, port 8000 with auto-reload enabled.
"""

import uvicorn
from app.core.config import settings

if __name__ == "__main__":
    print(f"Starting {settings.PROJECT_NAME} on http://localhost:{settings.SERVER_PORT}")
    print(f"Interactive API Docs available at http://localhost:{settings.SERVER_PORT}/docs")
    uvicorn.run("app.main:app", host=settings.SERVER_HOST, port=settings.SERVER_PORT, reload=True)
