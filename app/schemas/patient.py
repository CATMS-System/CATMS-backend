
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

# Insurance Provider
def normalize_email(v: str) -> str:
    """Emails are case-insensitive in practice; store them lowercase."""
    return v.lower()

class InsuranceProviderCreate(StrictModel):
    """Provider_Name and Email are UNIQUE in the DB; the service checks both
    and returns 409 instead of a raw database error"""
    provider_name: str = Field(..., min_length=1, max_length=100)
    contact_number: str
    email: EmailStr
    street_address: str = Field(..., min_length=1, max_length=150)
    city: str = Field(..., min_length=1, max_length=50)
    state_province: str = Field(..., min_length=1, max_length=50)
    postal_code: str

    @field_validator("contact_number")
    def _phone(cls, v: str) -> str:
        return normalize_phone(v)

    @field_validator("postal_code")
    def _postal(cls, v: str) -> str:
        return validate_postal(v)

    @field_validator("email")
    def _email(cls, v: str) -> str:
        return normalize_email(v)

class InsuranceProviderResponse(BaseModel):
    provider_id: int
    provider_name: str
    contact_number: str
    email: str
    street_address: str
    city: str
    state_province: str
    postal_code: str

# Insurance Policy

class InsurancePolicyCreate(StrictModel):
    """Policy_Number is only unique PER PROVIDER. patient_id comes from the URL, never from the body, and
    the status is set by the server """
    provider_id: int = Field(..., gt=0)
    policy_number: str = Field(..., min_length=1, max_length=50)
    policy_type: PolicyTypeEnum
    start_date: date
    end_date: date
    default_coverage_percentage: Decimal = Field(..., ge=0, le=100, decimal_places=2)

    @field_validator("start_date")
    def _start_sane(cls, v: date) -> date:
        return validate_policy_year(v, "start_date")

    @field_validator("end_date")
    def _end_sane_and_ordered(cls, v: date, info) -> date:
        v = validate_policy_year(v, "end_date")
        start = info.data.get("start_date")
        if start and v < start:
            raise ValueError("end_date cannot be before start_date")
        return v

class InsurancePolicyResponse(BaseModel):
    policy_id: int
    patient_id: int
    provider_id: int
    provider_name: str  # comes from a JOIN with Insurance_Provider
    policy_number: str
    policy_type: PolicyTypeEnum
    start_date: date
    end_date: date
    default_coverage_percentage: float
    policy_status: PolicyStatusEnum

    @computed_field
    @property
    def is_currently_valid(self) -> bool:
        """The stored status alone can go stale (nothing flips 'Active' to
        'Expired' on the end date), so a policy only counts as usable today
        if it is Active AND today falls inside its date range"""
        today = date.today()
        return (self.policy_status == PolicyStatusEnum.Active
            and self.start_date <= today <= self.end_date)

# Patient
class PatientCreate(StrictModel):
    """No account_id here on purpose: a client must never choose which login
    account a patient record is linked to. nic/date_of_birth/gender can only
    be set here (they are not editable later)"""
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    date_of_birth: date
    gender: GenderEnum
    nic: str
    contact_number: str
    email: EmailStr | None = None
    street_address: str = Field(..., min_length=1, max_length=150)
    city: str = Field(..., min_length=1, max_length=50)
    state_province: str = Field(..., min_length=1, max_length=50)
    postal_code: str
    emergency_contact: EmergencyContactCreate
    insurance_policy: InsurancePolicyCreate | None = None  # saved atomically

    @field_validator("nic")
    def _nic(cls, v: str) -> str:
        return normalize_nic(v)

    @field_validator("contact_number")
    def _phone(cls, v: str) -> str:
        return normalize_phone(v)

    @field_validator("date_of_birth")
    def _dob(cls, v: date) -> date:
        return validate_dob(v)

    @field_validator("postal_code")
    def _postal(cls, v: str) -> str:
        return validate_postal(v)

    @field_validator("email")
    def _email(cls, v: str | None) -> str | None:
        return normalize_email(v) if v is not None else v

class PatientUpdate(StrictModel):
    """Partial update: only fields that are sent get changed

    nic / date_of_birth / gender are deliberately absent (locked after
    registration); sending them is rejected by StrictModel

    last_known_updated_at is REQUIRED: the client sends back the `updated_at`
    it got from GET /patients/{id}. If someone else saved in between, the
    service answers 409 instead of silently overwriting their change """
    first_name: str | None = Field(None, min_length=1, max_length=50)
    last_name: str | None = Field(None, min_length=1, max_length=50)
    contact_number: str | None = None
    email: EmailStr | None = None  # explicit null clears the email
    street_address: str | None = Field(None, min_length=1, max_length=150)
    city: str | None = Field(None, min_length=1, max_length=50)
    state_province: str | None = Field(None, min_length=1, max_length=50)
    postal_code: str | None = None
    emergency_contact: EmergencyContactUpdate | None = None
    last_known_updated_at: datetime

    @field_validator("contact_number")
    def _phone(cls, v: str | None) -> str | None:
        return normalize_phone(v) if v is not None else v

    @field_validator("postal_code")
    def _postal(cls, v: str | None) -> str | None:
        return validate_postal(v) if v is not None else v

    @field_validator("email")
    def _email(cls, v: str | None) -> str | None:
        return normalize_email(v) if v is not None else v

class PatientSummaryResponse(BaseModel):
    """Lightweight row for search results (no nested data). Includes
    date_of_birth so same-named patients can be told apart at a glance"""
    patient_id: int
    first_name: str
    last_name: str
    date_of_birth: date
    nic: str
    contact_number: str
    registration_date: date

class PatientDetailResponse(BaseModel):
    """Full profile. Visit/appointment history is Member 3's domain and is intentionally not included here """
    patient_id: int
    first_name: str
    last_name: str
    date_of_birth: date
    gender: GenderEnum
    nic: str
    contact_number: str
    email: str | None
    street_address: str
    city: str
    state_province: str
    postal_code: str
    registration_date: date
    # The frontend reads this and sends it back as last_known_updated_at when it edits the patient (used to detect concurrent edits)
    updated_at: datetime
    # These reuse the response classes defined above, so those classes must stay above this one in the file
    emergency_contacts: list[EmergencyContactResponse] = []
    active_policies: list[InsurancePolicyResponse] = []

# Pagination 
T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    """List wrapper so the frontend can render 'Page 2 of 14'"""
    items: list[T]
    total: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    # ge=1 prevents a division by zero in total_pages below
    page_size: int = Field(..., ge=1)

    @computed_field
    @property
    def total_pages(self) -> int:
        return max(1, -(-self.total // self.page_size))  # ceiling division