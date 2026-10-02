from fastapi import APIRouter, Depends, HTTPException
import pymysql
from typing import List, Optional
from app.db.connection import get_db
from app.schemas.organization import StaffCreate, StaffResponse
from app.api.deps import get_current_user, require_roles
from app.schemas.user import UserAccount, SystemRoleEnum

router = APIRouter()

@router.get("", response_model=List[StaffResponse])
def get_staff(
    branch_id: Optional[int] = None,
    skip: int = 0, 
    limit: int = 100, 
    db: pymysql.Connection = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user)
):
    """Retrieve staff members (Option C: PyMySQL)."""
    with db.cursor() as cursor:
        if branch_id:
            cursor.execute(
                "SELECT * FROM Staff WHERE Branch_ID = %s LIMIT %s OFFSET %s",
                (branch_id, limit, skip)
            )
        else:
            cursor.execute(
                "SELECT * FROM Staff LIMIT %s OFFSET %s",
                (limit, skip)
            )
        result = cursor.fetchall()
        
    return [StaffResponse(**row) for row in result]

@router.post("", response_model=StaffResponse)
def create_staff(
    staff_in: StaffCreate, 
    db: pymysql.Connection = Depends(get_db),
    current_user: UserAccount = Depends(require_roles([SystemRoleEnum.Admin, SystemRoleEnum.Branch_Manager]))
):
    """Register a new staff member (Option C: PyMySQL)."""
    with db.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO Staff 
            (Account_ID, Branch_ID, First_Name, Last_Name, Job_Title, Contact_Number, Email, Employment_Status)
            VALUES 
            (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                staff_in.Account_ID, staff_in.Branch_ID, staff_in.First_Name, staff_in.Last_Name, 
                staff_in.Job_Title, staff_in.Contact_Number, staff_in.Email, staff_in.Employment_Status.value
            )
        )
        db.commit()
        cursor.execute("SELECT * FROM Staff WHERE Staff_ID = LAST_INSERT_ID()")
        new_staff = cursor.fetchone()
    return StaffResponse(**new_staff)
