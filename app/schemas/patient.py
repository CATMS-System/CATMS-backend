
"""
Pydantic schemas for Member 2's domain: Patient, Emergency_Contact,
Insurance_Provider, Insurance_Policy.
"""

from pydantic import BaseModel, ConfigDict, Field, EmailStr, field_validator, computed_field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Generic, TypeVar
import re


# Base Model

class StrictModel(BaseModel):
    """Shared base for 'Create'/'Update' schemas: trims whitespace and
    rejects unexpected fields (catches frontend typos)."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


# Enums
# Must match sql/01_schema.sql ENUM values exactly, including case.

class GenderEnum(str, Enum):
    Male = "Male"
    Female = "Female"
    Other = "Other"


class PolicyTypeEnum(str, Enum):
    Comprehensive = "Comprehensive"
    Outpatient_Only = "Outpatient_Only"
    Catastrophic = "Catastrophic"


class PolicyStatusEnum(str, Enum):
    Active = "Active"
    Expired = "Expired"
    Terminated = "Terminated"

# Shared Validators

PHONE_PATTERN = re.compile(r"^\+?\d[\d\s\-]{6,19}$")


def normalize_phone(v: str) -> str:
    """Validates format and strips spaces/dashes to a consistent value.
    Not used for duplicate-blocking (Contact_Number isn't unique — family
    members can share a phone), just for consistent storage."""
    if not PHONE_PATTERN.match(v):
        raise ValueError(
            "Phone number must be 7-20 digits, optionally starting with '+' "
            "and may contain spaces or dashes"
        )
    cleaned = re.sub(r"[\s\-]", "", v)
    if len(cleaned) > 20:  # defensive: DB column is VARCHAR(20)
        raise ValueError("Phone number too long after normalization")
    return cleaned