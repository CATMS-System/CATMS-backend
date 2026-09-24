from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

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

@app.get("/")
def root():
    return {"message": "Welcome to the CATMS API"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "database": "configured"}
