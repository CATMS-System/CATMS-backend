# public routes for patients who got an activation code from reception
# mounted at /api/v1/portal, no login needed (the code is the proof)
import pymysql
from fastapi import APIRouter, Depends

from app.api.deps import get_db
from app.core.rate_limit import portal_rate_limit
from app.schemas.patient import (
    PortalActivateRequest,
    PortalActivateResponse,
    PortalVerifyRequest,
    PortalVerifyResponse,
)
from app.services import portal_service

router = APIRouter(dependencies=[Depends(portal_rate_limit)])


# step 1: is the nic and code pair valid, and is this an activation or a reset
@router.post("/verify-code", response_model=PortalVerifyResponse)
def verify_code(data: PortalVerifyRequest, conn: pymysql.Connection = Depends(get_db)):
    return portal_service.verify_code(conn, data)


# step 2: choose the username and password (reset only needs the password)
@router.post("/activate", response_model=PortalActivateResponse, status_code=201)
def activate_account(data: PortalActivateRequest, conn: pymysql.Connection = Depends(get_db)):
    return portal_service.activate_account(conn, data)