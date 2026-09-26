from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from app.api.routers import auth, branches, staff

# Initialize FastAPI app
app = FastAPI(
    title="CATMS API",
    description="Clinic Appointment and Treatment Management System",
    version="1.0.0"
)

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Setup CORS (Cross-Origin Resource Sharing)
# This allows the React frontend to communicate with this backend API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For production, restrict this to the frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(branches.router, prefix="/api/v1/branches", tags=["branches"])
app.include_router(staff.router, prefix="/api/v1/staff", tags=["staff"])

@app.get("/")
def root():
    return {"message": "Welcome to the CATMS API"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "database": "configured"}
