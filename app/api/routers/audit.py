from fastapi import APIRouter, Depends, HTTPException
import pymysql
from typing import List, Optional
from app.db.connection import get_db
from app.schemas.audit import AuditLogResponse
from app.api.deps import require_roles
from app.schemas.user import UserAccount, SystemRoleEnum

router = APIRouter()

@router.get("/", response_model=List[AuditLogResponse])
def get_audit_logs(
    table_name: Optional[str] = None,
    skip: int = 0, 
    limit: int = 100, 
    db: pymysql.Connection = Depends(get_db),
    current_user: UserAccount = Depends(require_roles([SystemRoleEnum.Admin]))
):
    """Retrieve audit logs (Option C: PyMySQL)."""
    with db.cursor() as cursor:
        if table_name:
            cursor.execute(
                "SELECT * FROM Audit_Log WHERE Table_Name = %s ORDER BY Timestamp DESC LIMIT %s OFFSET %s",
                (table_name, limit, skip)
            )
        else:
            cursor.execute(
                "SELECT * FROM Audit_Log ORDER BY Timestamp DESC LIMIT %s OFFSET %s",
                (limit, skip)
            )
        result = cursor.fetchall()
    return [AuditLogResponse(**row) for row in result]
