from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.organization import Branch
from app.schemas.organization import BranchCreate, BranchResponse
from app.api.deps import require_roles
from app.models.user import UserAccount, SystemRoleEnum

router = APIRouter()

@router.get("/", response_model=List[BranchResponse])
def get_branches(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Retrieve all clinic branches."""
    branches = db.query(Branch).offset(skip).limit(limit).all()
    return branches

@router.post("/", response_model=BranchResponse)
def create_branch(
    branch_in: BranchCreate, 
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_roles([SystemRoleEnum.Admin]))
):
    """Create a new clinic branch (Admin only)."""
    db_branch = Branch(**branch_in.model_dump())
    db.add(db_branch)
    db.commit()
    db.refresh(db_branch)
    return db_branch
