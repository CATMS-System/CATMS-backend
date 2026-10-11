from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
import enum

class SystemRoleEnum(str, enum.Enum):
    Admin = "Admin"
    Branch_Manager = "Branch_Manager"
    Doctor = "Doctor"
    Receptionist = "Receptionist"
    Billing_Staff = "Billing_Staff"
    Patient = "Patient"

class AccountStatusEnum(str, enum.Enum):
    Active = "Active"
    Suspended = "Suspended"
    Deactivated = "Deactivated"

class UserAccount(BaseModel):
    Account_ID: int
    Username: str
    Password_Hash: str
    System_Role: SystemRoleEnum
    Account_Status: AccountStatusEnum
    Last_Login_At: Optional[datetime] = None

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
    Patient_ID: Optional[int] = None
    Staff_ID: Optional[int] = None
    Branch_ID: Optional[int] = None
    Doctor_ID: Optional[int] = None
    First_Name: Optional[str] = None
    Last_Name: Optional[str] = None
    Email: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# Token schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenPayload(BaseModel):
    sub: Optional[str] = None

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
