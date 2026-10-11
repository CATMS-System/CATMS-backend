from fastapi import APIRouter, Depends
import pymysql
from app.api.deps import get_db, get_current_user
from app.api.v1.endpoints import (
    appointments,
    audit,
    auth,
    billing,
    branches,
    consultations,
    doctors,
    insurance,
    patients,
    reports,
    staff,
    treatments,
)

api_router = APIRouter()


@api_router.get("/health", tags=["Health"])
def health_check(conn: pymysql.Connection = Depends(get_db)):
    """
    Health check endpoint verifying API service and PyMySQL database connectivity.
    """
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 AS status")
            result = cur.fetchone()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
        result = None

    return {
        "status": "healthy",
        "database": db_status,
        "query_result": result
    }

# Domain routers (all require authentication by default except public auth and health)
api_router.include_router(doctors.router, prefix="/doctors", tags=["Doctors"], dependencies=[Depends(get_current_user)])
api_router.include_router(doctors.specialties_router, prefix="/specialties", tags=["Specialties"], dependencies=[Depends(get_current_user)])
api_router.include_router(appointments.router, prefix="/appointments", tags=["Appointments"], dependencies=[Depends(get_current_user)])

api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(branches.router, prefix="/branches", tags=["Branches"], dependencies=[Depends(get_current_user)])
api_router.include_router(staff.router, prefix="/staff", tags=["Staff"], dependencies=[Depends(get_current_user)])
api_router.include_router(audit.router, prefix="/audit-logs", tags=["Audit Logs"], dependencies=[Depends(get_current_user)])
api_router.include_router(patients.router, prefix="/patients", tags=["Patients"], dependencies=[Depends(get_current_user)])
api_router.include_router(insurance.router, prefix="/insurance", tags=["Insurance"], dependencies=[Depends(get_current_user)])
api_router.include_router(treatments.router, prefix="/treatments", tags=["Treatments"], dependencies=[Depends(get_current_user)])
api_router.include_router(consultations.router, prefix="/consultations", tags=["Consultations"], dependencies=[Depends(get_current_user)])
api_router.include_router(billing.router, prefix="/billing", tags=["Billing"], dependencies=[Depends(get_current_user)])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"], dependencies=[Depends(get_current_user)])
