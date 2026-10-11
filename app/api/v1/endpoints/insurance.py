# insurance provider routes, mounted at /api/v1/insurance
import pymysql
from fastapi import APIRouter, Depends

from app.api.deps import get_db, require_roles
from app.schemas.user import SystemRoleEnum, UserAccount
from app.schemas.patient import InsuranceProviderCreate, InsuranceProviderResponse
from app.services import insurance_service

router = APIRouter()


@router.get(
    "/providers",
    response_model=list[InsuranceProviderResponse],
    dependencies=[Depends(require_roles([SystemRoleEnum.Admin, SystemRoleEnum.Branch_Manager, SystemRoleEnum.Billing_Staff, SystemRoleEnum.Receptionist, SystemRoleEnum.Doctor]))],
)
def list_providers(conn: pymysql.Connection = Depends(get_db)):
    return insurance_service.list_providers(conn)

@router.post(
    "/providers",
    response_model=InsuranceProviderResponse,
    status_code=201,
)
def create_provider(
    data: InsuranceProviderCreate,
    conn: pymysql.Connection = Depends(get_db),
    current_user: UserAccount = Depends(require_roles([SystemRoleEnum.Admin, SystemRoleEnum.Branch_Manager, SystemRoleEnum.Billing_Staff])),
):
    return insurance_service.create_provider(conn, data, account_id=current_user.Account_ID)
