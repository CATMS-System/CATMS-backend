from fastapi import APIRouter, Depends, HTTPException
import pymysql
from typing import List, Optional, Union
from app.db.connection import get_db
from app.schemas.organization import StaffCreate, StaffUpdate, StaffResponse
from app.schemas.staff import StaffPublicResponse
from app.api.deps import get_current_user, require_roles, get_staff_branch_id
from app.schemas.user import UserAccount, SystemRoleEnum

router = APIRouter()

@router.get("", response_model=List[Union[StaffResponse, StaffPublicResponse]])
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
        
    if current_user.System_Role in (SystemRoleEnum.Admin, SystemRoleEnum.Branch_Manager):
        return [StaffResponse(**row) for row in result]
    return [StaffPublicResponse(**row) for row in result]

@router.get("/{staff_id}", response_model=Union[StaffResponse, StaffPublicResponse])
def get_staff_by_id(
    staff_id: int,
    db: pymysql.Connection = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user)
):
    """Retrieve staff member by ID."""
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM Staff WHERE Staff_ID = %s", (staff_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Staff not found")

    if current_user.System_Role in (SystemRoleEnum.Admin, SystemRoleEnum.Branch_Manager):
        return StaffResponse(**row)
    return StaffPublicResponse(**row)

@router.post("", response_model=StaffResponse)
def create_staff(
    staff_in: StaffCreate, 
    db: pymysql.Connection = Depends(get_db),
    current_user: UserAccount = Depends(require_roles([SystemRoleEnum.Admin, SystemRoleEnum.Branch_Manager]))
):
    """Register a new staff member (Option C: PyMySQL)."""
    # Determine system role from explicit field or fallback to job title heuristics
    if staff_in.System_Role:
        role = staff_in.System_Role.value if hasattr(staff_in.System_Role, "value") else str(staff_in.System_Role)
    else:
        job_lower = staff_in.Job_Title.lower()
        if any(term in job_lower for term in ("doc", "cardio", "derma", "physician", "surgeon", "consultant", "pediatrician", "paediatrician", "general practitioner")):
            role = "Doctor"
        elif "manager" in job_lower:
            role = "Branch_Manager"
        elif "bill" in job_lower:
            role = "Billing_Staff"
        elif "admin" in job_lower:
            role = "Admin"
        else:
            role = "Receptionist"

    # Validate mandatory doctor attributes
    if role == "Doctor":
        if not staff_in.License_Number or staff_in.Standard_Consultation_Fee is None:
            raise HTTPException(
                status_code=422,
                detail="License number and standard consultation fee are required for doctors"
            )
        if staff_in.Standard_Consultation_Fee <= 0:
            raise HTTPException(
                status_code=422,
                detail="Standard consultation fee must be greater than 0"
            )

    try:
        with db.cursor() as cursor:
            account_id = staff_in.Account_ID
            if not account_id:
                base_username = staff_in.Username or f"{staff_in.First_Name.lower()}.{staff_in.Last_Name.lower()}"
                username = base_username
                cursor.execute("SELECT Account_ID FROM User_Account WHERE Username = %s", (username,))
                counter = 1
                while cursor.fetchone():
                    username = f"{base_username}{counter}"
                    cursor.execute("SELECT Account_ID FROM User_Account WHERE Username = %s", (username,))
                    counter += 1

                from app.core.security import get_password_hash
                raw_pwd = staff_in.Password or "Welcome123!"
                hashed_pwd = get_password_hash(raw_pwd)

                cursor.execute(
                    """
                    INSERT INTO User_Account (Username, Password_Hash, System_Role, Account_Status)
                    VALUES (%s, %s, %s, 'Active')
                    """,
                    (username, hashed_pwd, role)
                )
                account_id = cursor.lastrowid

            cursor.execute(
                """
                INSERT INTO Staff 
                (Account_ID, Branch_ID, First_Name, Last_Name, Job_Title, Contact_Number, Email, Employment_Status)
                VALUES 
                (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    account_id, staff_in.Branch_ID, staff_in.First_Name, staff_in.Last_Name, 
                    staff_in.Job_Title, staff_in.Contact_Number, staff_in.Email, staff_in.Employment_Status.value
                )
            )
            staff_id = cursor.lastrowid

            # Insert Doctor record and specialty mappings if role is Doctor
            if role == "Doctor":
                cursor.execute(
                    """
                    INSERT INTO Doctor (Doctor_ID, License_Number, Standard_Consultation_Fee)
                    VALUES (%s, %s, %s)
                    """,
                    (staff_id, staff_in.License_Number, staff_in.Standard_Consultation_Fee)
                )
                for sid in staff_in.Specialty_IDs or []:
                    cursor.execute(
                        """
                        INSERT INTO Doctor_Specialty (Doctor_ID, Specialty_ID)
                        VALUES (%s, %s)
                        """,
                        (staff_id, sid)
                    )

            db.commit()
            cursor.execute("SELECT * FROM Staff WHERE Staff_ID = %s", (staff_id,))
            new_staff = cursor.fetchone()

        if role == "Doctor":
            new_staff["System_Role"] = SystemRoleEnum.Doctor
            new_staff["License_Number"] = staff_in.License_Number
            new_staff["Standard_Consultation_Fee"] = staff_in.Standard_Consultation_Fee
            new_staff["Specialty_IDs"] = staff_in.Specialty_IDs or []

        return StaffResponse(**new_staff)

    except HTTPException:
        db.rollback()
        raise
    except pymysql.err.IntegrityError as e:
        db.rollback()
        errno = e.args[0] if len(e.args) > 0 else 0
        errmsg = str(e)
        if errno == 1062:
            if "License_Number" in errmsg:
                raise HTTPException(
                    status_code=409,
                    detail=f"Doctor with license number '{staff_in.License_Number}' already exists."
                )
            raise HTTPException(
                status_code=409,
                detail=f"Conflict: Duplicate record already exists ({errmsg})"
            )
        elif errno == 1452:
            raise HTTPException(
                status_code=404,
                detail=f"Referenced foreign key not found ({errmsg})"
            )
        raise HTTPException(
            status_code=422,
            detail=f"Database integrity error: {errmsg}"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create staff member: {str(e)}"
        )

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
            
        # Ensure branch managers can only update their own branch staff
        if current_user.System_Role == SystemRoleEnum.Branch_Manager:
            manager_branch_id = get_staff_branch_id(db, current_user)
            if not manager_branch_id or existing_staff["Branch_ID"] != manager_branch_id:
                raise HTTPException(
                    status_code=403,
                    detail="Branch managers can only modify staff within their own branch.",
                )
            
        cursor.execute(f"UPDATE Staff SET {set_clause} WHERE Staff_ID = %s", tuple(values))
        db.commit()
        
        cursor.execute("SELECT * FROM Staff WHERE Staff_ID = %s", (staff_id,))
        updated_staff = cursor.fetchone()
        
    return StaffResponse(**updated_staff)
