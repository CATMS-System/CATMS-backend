"""
Unit tests for Audit Log schema parsing and validation.
Verifies PyMySQL JSON string serialization compatibility with Pydantic v2.
"""

from datetime import datetime
import json
from app.schemas.audit import AuditLogResponse, ActionTypeEnum


def test_audit_log_response_parses_json_string():
    """Validates that a JSON-encoded string from PyMySQL is parsed into a dictionary."""
    old_val = json.dumps({"Employment_Status": "Active", "Job_Title": "Cardiologist"})
    new_val = json.dumps({"Employment_Status": "On_Leave", "Job_Title": "Cardiologist"})

    record = AuditLogResponse(
        Audit_ID=101,
        Account_ID=1,
        Branch_ID=2,
        Table_Name="Staff",
        Record_ID="5",
        Action_Type=ActionTypeEnum.UPDATE,
        Timestamp=datetime.now(),
        Old_Value=old_val,
        New_Value=new_val
    )

    assert isinstance(record.Old_Value, dict)
    assert record.Old_Value["Employment_Status"] == "Active"
    assert isinstance(record.New_Value, dict)
    assert record.New_Value["Employment_Status"] == "On_Leave"


def test_audit_log_response_handles_none():
    """Validates that None values for Old_Value and New_Value are accepted without error."""
    record = AuditLogResponse(
        Audit_ID=102,
        Account_ID=1,
        Branch_ID=None,
        Table_Name="Patient",
        Record_ID="10",
        Action_Type=ActionTypeEnum.INSERT,
        Timestamp=datetime.now(),
        Old_Value=None,
        New_Value=None
    )

    assert record.Old_Value is None
    assert record.New_Value is None
