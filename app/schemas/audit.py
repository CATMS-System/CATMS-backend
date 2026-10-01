from pydantic import BaseModel, ConfigDict
from typing import Optional, Any, Dict
from datetime import datetime
import enum

class ActionTypeEnum(str, enum.Enum):
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
class AuditLogResponse(BaseModel):
    Audit_ID: int
    Account_ID: int
    Branch_ID: Optional[int]
    Table_Name: str
    Record_ID: str
    Action_Type: ActionTypeEnum
    Timestamp: datetime
    Old_Value: Optional[Dict[str, Any]]
    New_Value: Optional[Dict[str, Any]]

    model_config = ConfigDict(from_attributes=True)
