from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.api.deps import get_db

api_router = APIRouter()


@api_router.get("/health", tags=["Health"])
def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint verifying API service and database connectivity.
    """
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status": "healthy",
        "database": db_status
    }

# Team members will mount their domain routers here:
# api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
# api_router.include_router(patients.router, prefix="/patients", tags=["Patients"])
# api_router.include_router(doctors.router, prefix="/doctors", tags=["Doctors"])
# api_router.include_router(appointments.router, prefix="/appointments", tags=["Appointments"])
# api_router.include_router(consultations.router, prefix="/consultations", tags=["Consultations"])
# api_router.include_router(billing.router, prefix="/billing", tags=["Billing"])
# api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])
