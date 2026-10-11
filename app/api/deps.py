import pymysql
from fastapi import Depends, HTTPException, status
from jose import jwt, JWTError
from app.core.security import oauth2_scheme
from app.core.config import settings
from app.db.connection import get_db
from app.schemas.user import UserAccount, SystemRoleEnum
from app.schemas.user import TokenPayload

__all__ = [
    "get_db",
    "get_current_user",
    "require_roles",
    "get_own_patient_id",
    "get_staff_branch_id",
    "get_own_doctor_id",
    "doctor_has_treated_patient",
]

def get_current_user(db: pymysql.Connection = Depends(get_db), token: str = Depends(oauth2_scheme)) -> UserAccount:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        token_data = TokenPayload(**payload)
        if token_data.sub is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM User_Account WHERE Username = %s", (token_data.sub,))
        user_row = cursor.fetchone()
    
    if user_row is None:
        raise credentials_exception
        
    user = UserAccount(**user_row)  # type: ignore
    if user.Account_Status != "Active":
        raise HTTPException(status_code=400, detail="Inactive user")

    with db.cursor() as cursor:
        cursor.execute(
            "SET @app_account_id = %s, @current_account_id = %s",
            (user.Account_ID, user.Account_ID)
        )
        cursor.execute("SELECT Branch_ID FROM Staff WHERE Account_ID = %s", (user.Account_ID,))
        st_row = cursor.fetchone()
        if st_row and st_row.get("Branch_ID"):
            cursor.execute(
                "SET @app_branch_id = %s, @current_branch_id = %s",
                (st_row["Branch_ID"], st_row["Branch_ID"])
            )
        else:
            cursor.execute("SET @app_branch_id = NULL, @current_branch_id = NULL")

    return user

def require_roles(allowed_roles: list[SystemRoleEnum]):
    def role_checker(current_user: UserAccount = Depends(get_current_user)):
        if current_user.System_Role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted for this role"
            )
        return current_user
    return role_checker

def get_own_patient_id(db: pymysql.Connection, user: UserAccount) -> int | None:
    with db.cursor() as cursor:
        cursor.execute("SELECT Patient_ID FROM Patient WHERE Account_ID = %s", (user.Account_ID,))
        row = cursor.fetchone()
        return row["Patient_ID"] if row else None

def get_staff_branch_id(db: pymysql.Connection, user: UserAccount) -> int | None:
    with db.cursor() as cursor:
        cursor.execute("SELECT Branch_ID FROM Staff WHERE Account_ID = %s", (user.Account_ID,))
        row = cursor.fetchone()
        return row["Branch_ID"] if row else None

def get_own_doctor_id(db: pymysql.Connection, user: UserAccount) -> int | None:
    with db.cursor() as cursor:
        cursor.execute(
            """
            SELECT d.Doctor_ID 
            FROM Doctor d 
            JOIN Staff s ON d.Doctor_ID = s.Staff_ID 
            WHERE s.Account_ID = %s
            """,
            (user.Account_ID,)
        )
        row = cursor.fetchone()
        return row["Doctor_ID"] if row else None

def doctor_has_treated_patient(db: pymysql.Connection, doctor_id: int, patient_id: int) -> bool:
    with db.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1 FROM Appointment 
            WHERE Doctor_ID = %s AND Patient_ID = %s 
            LIMIT 1
            """,
            (doctor_id, patient_id)
        )
        return cursor.fetchone() is not None

