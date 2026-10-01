from pydantic import BaseModel, ConfigDict, EmailStr
from typing import Optional, List
import enum

class EmploymentStatusEnum(str, enum.Enum):
    Active = "Active"
    On_Leave = "On_Leave"
    Resigned = "Resigned"
    Terminated = "Terminated"
# --- Branch Schemas ---
class BranchBase(BaseModel):
    Branch_Name: str
    Street_Address: str
    City: str
    State_Province: str
    Postal_Code: str
    Contact_Number: str
    Email: EmailStr
    Manager_Staff_ID: Optional[int] = None  # create a Branch first without a manager, and assign the manager later.

class BranchCreate(BranchBase):
    pass

class BranchResponse(BranchBase):
    Branch_ID: int
    model_config = ConfigDict(from_attributes=True)

# --- Staff Schemas ---
class StaffBase(BaseModel):
    First_Name: str
    Last_Name: str
    Job_Title: str
    Contact_Number: str
    Email: EmailStr
    Employment_Status: EmploymentStatusEnum = EmploymentStatusEnum.Active
    Branch_ID: int

class StaffCreate(StaffBase):
    Account_ID: int

class StaffResponse(StaffBase):
    Staff_ID: int
    Account_ID: int
    model_config = ConfigDict(from_attributes=True)
