from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
import pymysql
from app.db.connection import get_db
from app.schemas.user import UserAccount, Token, UserResponse, SystemRoleEnum
from app.core.security import verify_password, create_access_token
from app.api.deps import get_current_user
from app.core.config import settings

router = APIRouter()

@router.post("/login", response_model=Token)
def login_access_token(db: pymysql.Connection = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    """OAuth2 compatible token login (Option C: PyMySQL)"""
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM User_Account WHERE Username = %s", (form_data.username,))
        user_row = cursor.fetchone()
    
    if not user_row or not verify_password(form_data.password, user_row['Password_Hash']):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    elif user_row['Account_Status'] != "Active":
        raise HTTPException(status_code=400, detail="Inactive user")
        
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user_row['Username'], expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
def read_users_me(
    current_user: UserAccount = Depends(get_current_user),
    db: pymysql.Connection = Depends(get_db),
):
    """Get current user profile enriched with patient or staff details"""
    user_data = current_user.model_dump()
    try:
        with db.cursor() as cursor:
            if current_user.System_Role == SystemRoleEnum.Patient:
                cursor.execute(
                    "SELECT Patient_ID, First_Name, Last_Name, Email FROM Patient WHERE Account_ID = %s",
                    (current_user.Account_ID,),
                )
                patient = cursor.fetchone()
                if patient:
                    user_data["Patient_ID"] = patient.get("Patient_ID")
                    user_data["First_Name"] = patient.get("First_Name")
                    user_data["Last_Name"] = patient.get("Last_Name")
                    if patient.get("Email"):
                        user_data["Email"] = patient.get("Email")
            else:
                cursor.execute(
                    "SELECT Staff_ID, Branch_ID, First_Name, Last_Name, Email FROM Staff WHERE Account_ID = %s",
                    (current_user.Account_ID,),
                )
                staff = cursor.fetchone()
                if staff:
                    user_data["Staff_ID"] = staff.get("Staff_ID")
                    user_data["Branch_ID"] = staff.get("Branch_ID")
                    user_data["First_Name"] = staff.get("First_Name")
                    user_data["Last_Name"] = staff.get("Last_Name")
                    if staff.get("Email"):
                        user_data["Email"] = staff.get("Email")
                    if current_user.System_Role == SystemRoleEnum.Doctor:
                        cursor.execute(
                            "SELECT Doctor_ID FROM Doctor WHERE Doctor_ID = %s",
                            (staff.get("Staff_ID"),),
                        )
                        doc = cursor.fetchone()
                        if doc:
                            user_data["Doctor_ID"] = doc.get("Doctor_ID")
    except Exception:
        pass

    return UserResponse(**user_data)
