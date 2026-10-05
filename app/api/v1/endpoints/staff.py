from fastapi import APIRouter, Depends, HTTPException
import pymysql
from typing import List, Optional
from app.db.connection import get_db
from app.schemas.organization import StaffCreate, StaffUpdate, StaffResponse
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

@router.put("/{staff_id}", response_model=StaffResponse)
def update_staff(
    staff_id: int,
    staff_in: StaffUpdate,
    db: pymysql.Connection = Depends(get_db),
    current_user: UserAccount = Depends(require_roles([SystemRoleEnum.Admin, SystemRoleEnum.Branch_Manager]))
):
    """Update staff details (Option C: PyMySQL)."""
    update_data = staff_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No data provided to update")
        
    # If enum, we might need to convert it to string
    if "Employment_Status" in update_data:
        update_data["Employment_Status"] = update_data["Employment_Status"].value
        
    set_clause = ", ".join([f"{key} = %s" for key in update_data.keys()])
    values = list(update_data.values())
    values.append(staff_id)
    
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM Staff WHERE Staff_ID = %s", (staff_id,))
        existing_staff = cursor.fetchone()
        if not existing_staff:
            raise HTTPException(status_code=404, detail="Staff not found")
            
        # Optional: Ensure branch managers can only update their own branch staff
        if current_user.System_Role == SystemRoleEnum.Branch_Manager:
            # Check if staff belongs to manager's branch
            pass
            
        cursor.execute(f"UPDATE Staff SET {set_clause} WHERE Staff_ID = %s", tuple(values))
        db.commit()
        
        cursor.execute("SELECT * FROM Staff WHERE Staff_ID = %s", (staff_id,))
        updated_staff = cursor.fetchone()
        
    return StaffResponse(**updated_staff)
