from fastapi import APIRouter, Depends, HTTPException
import pymysql
from typing import List
from app.db.connection import get_db
from app.schemas.organization import BranchCreate, BranchUpdate, BranchResponse
from app.api.deps import require_roles
from app.schemas.user import UserAccount, SystemRoleEnum

router = APIRouter()

@router.get("", response_model=List[BranchResponse])
def get_branches(skip: int = 0, limit: int = 100, db: pymysql.Connection = Depends(get_db)):
    """Retrieve all clinic branches (Option C: PyMySQL)."""
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM Branch LIMIT %s OFFSET %s", (limit, skip))
        result = cursor.fetchall()
    return [BranchResponse(**row) for row in result]

@router.post("", response_model=BranchResponse)
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

@router.put("/{branch_id}", response_model=BranchResponse)
def update_branch(
    branch_id: int,
    branch_in: BranchUpdate,
    db: pymysql.Connection = Depends(get_db),
    current_user: UserAccount = Depends(require_roles([SystemRoleEnum.Admin]))
):
    """Update clinic branch details (Option C: PyMySQL)."""
    update_data = branch_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No data provided to update")
        
    set_clause = ", ".join([f"{key} = %s" for key in update_data.keys()])
    values = list(update_data.values())
    values.append(branch_id)
    
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM Branch WHERE Branch_ID = %s", (branch_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Branch not found")
            
        cursor.execute(f"UPDATE Branch SET {set_clause} WHERE Branch_ID = %s", tuple(values))
        db.commit()
        
        cursor.execute("SELECT * FROM Branch WHERE Branch_ID = %s", (branch_id,))
        updated_branch = cursor.fetchone()
        
    return BranchResponse(**updated_branch)
