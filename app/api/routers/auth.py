from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
import pymysql
from app.db.connection import get_db
from app.schemas.user import UserAccount
from app.schemas.user import Token, UserResponse
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
def read_users_me(current_user: UserAccount = Depends(get_current_user)):
    """Get current user profile"""
    return current_user
