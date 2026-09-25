from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from app.models.user import SystemRoleEnum, AccountStatusEnum

# Base properties for read/write
class UserBase(BaseModel):
    Username: str
    System_Role: SystemRoleEnum

# Schema for creating a new user
class UserCreate(UserBase):
    Password: str

# Schema for updating a user
class UserUpdate(BaseModel):
    Password: Optional[str] = None
    System_Role: Optional[SystemRoleEnum] = None
    Account_Status: Optional[AccountStatusEnum] = None

# Schema for returning user data (omits password hash)
class UserResponse(UserBase):
    Account_ID: int
    Account_Status: AccountStatusEnum
    Last_Login_At: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

# Token schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenPayload(BaseModel):
    sub: Optional[str] = None
