import pymysql
from fastapi import Depends, HTTPException, status
from jose import jwt, JWTError
from app.core.security import oauth2_scheme
from app.core.config import settings
from app.db.connection import get_db
from app.schemas.user import UserAccount, SystemRoleEnum
from app.schemas.user import TokenPayload

__all__ = ["get_db", "get_current_user", "require_roles"]

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
        
    user = UserAccount(**user_row)
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
