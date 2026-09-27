from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.audit import AuditLog
from app.schemas.audit import AuditLogResponse
from app.api.deps import require_roles
from app.models.user import UserAccount, SystemRoleEnum

router = APIRouter()

@router.get("/", response_model=List[AuditLogResponse])
def get_audit_logs(
    table_name: Optional[str] = None,
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_roles([SystemRoleEnum.Admin]))
):
    """Retrieve audit logs (Admin only)."""
    query = db.query(AuditLog)
    if table_name:
        query = query.filter(AuditLog.Table_Name == table_name)
    return query.order_by(AuditLog.Timestamp.desc()).offset(skip).limit(limit).all()
