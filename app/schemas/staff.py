from pydantic import BaseModel, ConfigDict
from app.schemas.organization import (
    EmploymentStatusEnum,
    StaffBase,
    StaffCreate,
    StaffUpdate,
    StaffResponse,
)


class StaffPublicResponse(BaseModel):
    Staff_ID: int
    First_Name: str
    Last_Name: str
    Job_Title: str
    Branch_ID: int
    Employment_Status: EmploymentStatusEnum = EmploymentStatusEnum.Active

    model_config = ConfigDict(from_attributes=True)


__all__ = [
    "EmploymentStatusEnum",
    "StaffBase",
    "StaffCreate",
    "StaffUpdate",
    "StaffResponse",
    "StaffPublicResponse",
]
