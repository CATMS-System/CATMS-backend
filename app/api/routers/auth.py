from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import UserAccount
from app.schemas.user import Token, UserResponse
from app.core.security import verify_password, create_access_token
from app.api.deps import get_current_user
from app.config import settings

router = APIRouter()

@router.post("/login", response_model=Token)
def login_access_token(db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    user = db.query(UserAccount).filter(UserAccount.Username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.Password_Hash):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    elif user.Account_Status != "Active":
        raise HTTPException(status_code=400, detail="Inactive user")
        
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.Username, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: UserAccount = Depends(get_current_user)):
    """
    Get current user profile
    """
    return current_user
