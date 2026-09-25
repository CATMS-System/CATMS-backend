from fastapi import Depends, HTTPException, status
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from app.core.security import oauth2_scheme
from app.config import settings
from app.database import get_db
from app.models.user import UserAccount, SystemRoleEnum
from app.schemas.user import TokenPayload

def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> UserAccount:
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
        
    user = db.query(UserAccount).filter(UserAccount.Username == token_data.sub).first()
    if user is None:
        raise credentials_exception
    if user.Account_Status != "Active":
        raise HTTPException(status_code=400, detail="Inactive user")
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
