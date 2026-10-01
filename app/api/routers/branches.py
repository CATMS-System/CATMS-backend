from fastapi import APIRouter, Depends, HTTPException
import pymysql
from typing import List
from app.db.connection import get_db
from app.schemas.organization import BranchCreate, BranchResponse
from app.api.deps import require_roles
from app.schemas.user import UserAccount, SystemRoleEnum

router = APIRouter()

@router.get("/", response_model=List[BranchResponse])
def get_branches(skip: int = 0, limit: int = 100, db: pymysql.Connection = Depends(get_db)):
    """Retrieve all clinic branches (Option C: PyMySQL)."""
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM Branch LIMIT %s OFFSET %s", (limit, skip))
        result = cursor.fetchall()
    return [BranchResponse(**row) for row in result]

@router.post("/", response_model=BranchResponse)
def create_branch(
    branch_in: BranchCreate, 
    db: pymysql.Connection = Depends(get_db),
    current_user: UserAccount = Depends(require_roles([SystemRoleEnum.Admin]))
):
    """Create a new clinic branch (Option C: PyMySQL)."""
    with db.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO Branch 
            (Branch_Name, Street_Address, City, State_Province, Postal_Code, Contact_Number, Email, Manager_Staff_ID)
            VALUES 
            (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                branch_in.Branch_Name, branch_in.Street_Address, branch_in.City, 
                branch_in.State_Province, branch_in.Postal_Code, branch_in.Contact_Number, 
                branch_in.Email, branch_in.Manager_Staff_ID
            )
        )
        db.commit()
        cursor.execute("SELECT * FROM Branch WHERE Branch_ID = LAST_INSERT_ID()")
        new_branch = cursor.fetchone()
    return BranchResponse(**new_branch)
