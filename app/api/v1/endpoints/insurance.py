# insurance provider routes, mounted at /api/v1/insurance
# role checks later: list for any logged in user, create for Admin only
import pymysql
from fastapi import APIRouter, Depends

from app.api.deps import get_db
from app.schemas.patient import InsuranceProviderResponse, InsuranceProviderCreate
from app.services import insurance_service

router = APIRouter()


@router.get("/providers", response_model=list[InsuranceProviderResponse])
def list_providers(conn: pymysql.Connection = Depends(get_db)):
    return insurance_service.list_providers(conn)

@router.post("/providers", response_model=InsuranceProviderResponse, status_code=201)
def create_provider(data: InsuranceProviderCreate, conn: pymysql.Connection = Depends(get_db)):
    return insurance_service.create_provider(conn, data)