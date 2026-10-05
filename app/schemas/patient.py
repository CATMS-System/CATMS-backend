
""" Pydantic schemas for Member 2's domain: Patient, Emergency_Contact, Insurance_Provider, Insurance_Policy """

from pydantic import BaseModel, ConfigDict, Field, EmailStr, field_validator, computed_field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Generic, TypeVar
import re


# Base Model
class StrictModel(BaseModel):
    """Shared base for 'Create'/'Update' schemas: trims whitespace and
    rejects unexpected fields"""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


# Enums
# matching sql/01_schema.sql ENUM values exactly, including case.

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
    members can share a phone), just for consistent storage """
    if not PHONE_PATTERN.match(v):
        raise ValueError(
            "Phone number must be 7-20 digits, optionally starting with '+' "
            "and may contain spaces or dashes"
        )
    cleaned = re.sub(r"[\s\-]", "", v)
    if len(cleaned) > 20:  # defensive: DB column is VARCHAR(20)
        raise ValueError("Phone number too long after normalization")
    return cleaned



def normalize_nic(v: str) -> str:
    """Validates Sri Lankan NIC format and uppercases the V/X suffix, so
    '852140938v' and '852140938V' are treated as one value """
    v = v.strip().upper()
    if not re.match(r"^(\d{9}[VX]|\d{12})$", v):
        raise ValueError("NIC must be old format (9 digits + V or X) or new 12-digit format")
    return v

MIN_BIRTH_YEAR = date.today().year - 120


def validate_dob(v: date) -> date:
    """Rejects future dates and ages implying over 120 years — almost always a typo """
    if v > date.today():
        raise ValueError("Date of birth cannot be in the future")
    if v.year < MIN_BIRTH_YEAR:
        raise ValueError(f"Date of birth implies an unrealistic age (before {MIN_BIRTH_YEAR})")
    return v

SRI_LANKA_POSTAL_PATTERN = re.compile(r"^\d{5}$")


def validate_postal(v: str) -> str:
    """Sri Lankan postal codes are exactly 5 digits"""
    if not SRI_LANKA_POSTAL_PATTERN.match(v):
        raise ValueError("Postal code must be exactly 5 digits")
    return v

MIN_POLICY_YEAR = 2000  # sanity floor — catches typos like "202" or "1926"
MAX_POLICY_YEAR = date.today().year + 50  # sanity ceiling on end_date typos

def validate_policy_year(v: date, field_name: str) -> date:
    """Catches obvious typo years in insurance policy dates"""
    if v.year < MIN_POLICY_YEAR:
        raise ValueError(f"{field_name} year looks like a typo (before {MIN_POLICY_YEAR})")
    if v.year > MAX_POLICY_YEAR:
        raise ValueError(f"{field_name} year looks like a typo (after {MAX_POLICY_YEAR})")
    return v

# Emergency Contact
class EmergencyContactCreate(StrictModel):
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    relationship_to_patient: str = Field(..., min_length=1, max_length=50)
    contact_number: str
    street_address: str | None = Field(None, max_length=150)
    city: str | None = Field(None, max_length=50)
    postal_code: str | None = Field(None, max_length=20)

    @field_validator("contact_number")
    def _phone(cls, v: str) -> str:
        return normalize_phone(v)

    @field_validator("postal_code")
    def _postal(cls, v: str | None) -> str | None:
        return validate_postal(v) if v is not None else v

class EmergencyContactUpdate(StrictModel):
    """Edits ONE emergency contact. The id says which one, because a patient
    can have several. The service checks the contact really belongs to the
    patient being updated """
    emergency_contact_id: int = Field(..., gt=0)
    first_name: str | None = Field(None, min_length=1, max_length=50)
    last_name: str | None = Field(None, min_length=1, max_length=50)
    relationship_to_patient: str | None = Field(None, min_length=1, max_length=50)
    contact_number: str | None = None
    street_address: str | None = Field(None, max_length=150)
    city: str | None = Field(None, max_length=50)
    postal_code: str | None = Field(None, max_length=20)

    @field_validator("contact_number")
    def _phone(cls, v: str | None) -> str | None:
        return normalize_phone(v) if v is not None else v

    @field_validator("postal_code")
    def _postal(cls, v: str | None) -> str | None:
        return validate_postal(v) if v is not None else v

class EmergencyContactResponse(BaseModel):
    emergency_contact_id: int
    patient_id: int
    first_name: str
    last_name: str
    relationship_to_patient: str
    contact_number: str
    street_address: str | None
    city: str | None
    postal_code: str | None