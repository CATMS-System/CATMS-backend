from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional, Any, Dict, Union
from datetime import datetime
import enum
import json

class ActionTypeEnum(str, enum.Enum):
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
class AuditLogResponse(BaseModel):
    Audit_ID: int
    Account_ID: int
    Branch_ID: Optional[int] = None
    Table_Name: str
    Record_ID: str
    Action_Type: ActionTypeEnum
    Timestamp: datetime
    Old_Value: Optional[Union[Dict[str, Any], str]] = None
    New_Value: Optional[Union[Dict[str, Any], str]] = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("Old_Value", "New_Value", mode="before")
    @classmethod
    def parse_json_value(cls, v: Any) -> Optional[Dict[str, Any]]:
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return None
        if isinstance(v, dict):
            return v
        return None
