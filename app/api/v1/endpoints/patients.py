# patient routes, mounted at /api/v1/patients
# register, update: Admin and Receptionist
# search and read: Admin, Branch_Manager, Receptionist, Doctor
# policies: Admin, Branch_Manager, Receptionist, Doctor, Billing_Staff
import pymysql
from fastapi import APIRouter, Depends, Path, Query

from app.api.deps import get_db, require_roles, get_current_user
from app.schemas.user import SystemRoleEnum, UserAccount
from app.schemas.patient import (
    InsurancePolicyCreate,
    InsurancePolicyResponse,
    PaginatedResponse,
    PatientCreate,
    PatientDetailResponse,
    PatientSummaryResponse,
    PatientUpdate,
)
from app.services import insurance_service, patient_service

router = APIRouter()


# patient, one emergency contact and an optional policy are saved together
@router.post(
    "",
    response_model=PatientDetailResponse,
    status_code=201,
    dependencies=[Depends(require_roles([SystemRoleEnum.Admin, SystemRoleEnum.Receptionist]))],
)
def register_patient(
    data: PatientCreate,
    conn: pymysql.Connection = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return patient_service.register_patient(conn, data, account_id=current_user.Account_ID)

# search by name, nic, phone or patient id, empty search lists everyone
@router.get(
    "",
    response_model=PaginatedResponse[PatientSummaryResponse],
    dependencies=[Depends(require_roles([SystemRoleEnum.Admin, SystemRoleEnum.Branch_Manager, SystemRoleEnum.Receptionist, SystemRoleEnum.Doctor]))],
)
def search_patients(
    query: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    conn: pymysql.Connection = Depends(get_db),
):
    return patient_service.search_patients(conn, query, page, page_size)

@router.get(
    "/{patient_id}",
    response_model=PatientDetailResponse,
    dependencies=[Depends(require_roles([SystemRoleEnum.Admin, SystemRoleEnum.Branch_Manager, SystemRoleEnum.Receptionist, SystemRoleEnum.Doctor]))],
)
def get_patient(patient_id: int = Path(..., ge=1), conn: pymysql.Connection = Depends(get_db)):
    return patient_service.get_patient_detail(conn, patient_id)

# client sends last_known_updated_at, the updated_at it got from the get route
@router.put(
    "/{patient_id}",
    response_model=PatientDetailResponse,
    dependencies=[Depends(require_roles([SystemRoleEnum.Admin, SystemRoleEnum.Receptionist]))],
)
def update_patient(
    data: PatientUpdate,
    patient_id: int = Path(..., ge=1),
    conn: pymysql.Connection = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return patient_service.update_patient(conn, patient_id, data, account_id=current_user.Account_ID)

@router.get(
    "/{patient_id}/policies",
    response_model=list[InsurancePolicyResponse],
    dependencies=[Depends(require_roles([SystemRoleEnum.Admin, SystemRoleEnum.Branch_Manager, SystemRoleEnum.Receptionist, SystemRoleEnum.Doctor, SystemRoleEnum.Billing_Staff]))],
)
def list_policies(patient_id: int = Path(..., ge=1), conn: pymysql.Connection = Depends(get_db)):
    return insurance_service.list_patient_policies(conn, patient_id)

@router.post(
    "/{patient_id}/policies",
    response_model=InsurancePolicyResponse,
    status_code=201,
    dependencies=[Depends(require_roles([SystemRoleEnum.Admin, SystemRoleEnum.Receptionist, SystemRoleEnum.Billing_Staff]))],
)
def attach_policy(
    data: InsurancePolicyCreate,
    patient_id: int = Path(..., ge=1),
    conn: pymysql.Connection = Depends(get_db),
):
    return insurance_service.attach_policy(conn, patient_id, data)
