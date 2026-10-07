# patient routes, mounted at /api/v1/patients
# role checks are not added yet because login (member 1) does not exist
# later add to each route: dependencies=[Depends(require_roles(["Admin", "Receptionist"]))]
# and pass account_id=current_user["account_id"] to the service so changes go to Audit_Log
# register, update, attach policy: Admin and Receptionist
# search and read: Admin, Branch_Manager, Receptionist, Doctor
import pymysql
from fastapi import APIRouter, Depends, Query, Path

from app.api.deps import get_db
from app.schemas.patient import (PaginatedResponse, PatientCreate, PatientDetailResponse, PatientSummaryResponse,)
from app.services import patient_service

router = APIRouter()


# patient, one emergency contact and an optional policy are saved together
@router.post("", response_model=PatientDetailResponse, status_code=201)
def register_patient(data: PatientCreate, conn: pymysql.Connection = Depends(get_db)):
    return patient_service.register_patient(conn, data)

# search by name, nic, phone or patient id, empty search lists everyone
@router.get("", response_model=PaginatedResponse[PatientSummaryResponse])
def search_patients(
    query: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    conn: pymysql.Connection = Depends(get_db),
):
    return patient_service.search_patients(conn, query, page, page_size)

@router.get("/{patient_id}", response_model=PatientDetailResponse)
def get_patient(patient_id: int = Path(..., ge=1), conn: pymysql.Connection = Depends(get_db)):
    return patient_service.get_patient_detail(conn, patient_id)