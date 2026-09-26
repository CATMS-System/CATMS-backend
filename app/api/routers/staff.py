from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.organization import Staff
from app.schemas.organization import StaffCreate, StaffResponse
from app.api.deps import get_current_user, require_roles
from app.models.user import UserAccount, SystemRoleEnum

router = APIRouter()

@router.get("/", response_model=List[StaffResponse])
def get_staff(
    branch_id: Optional[int] = None,
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user)
):
    """Retrieve staff members, optionally filtered by branch."""
    query = db.query(Staff)
    if branch_id:
        query = query.filter(Staff.Branch_ID == branch_id)
    return query.offset(skip).limit(limit).all()

@router.post("/", response_model=StaffResponse)
def create_staff(
    staff_in: StaffCreate, 
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_roles([SystemRoleEnum.Admin, SystemRoleEnum.Branch_Manager]))
):
    """Register a new staff member."""
    db_staff = Staff(**staff_in.model_dump())
    db.add(db_staff)
    db.commit()
    db.refresh(db_staff)
    return db_staff
