"""
Pydantic schemas for Clinical Consultations domain (Member 4).
Includes request schemas for recording clinical notes, patient vitals,
and prescribing itemized treatments.
"""

from datetime import date
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class VitalsIn(BaseModel):
    """Patient vital signs recorded during consultation."""
    bp: Optional[str] = None
    heart_rate: Optional[int] = None
    temperature: Optional[float] = None
    spo2: Optional[int] = None
    weight: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class PrescribedItemIn(BaseModel):
    """Itemized treatment prescription within a consultation."""
    treatment_id: int
    quantity: int = Field(default=1, gt=0, description="Quantity must be greater than zero")
    instructions: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ConsultationCreate(BaseModel):
    """Request payload to record a consultation and prescribe treatments."""
    appointment_id: int
    diagnosis: str = Field(..., min_length=1, description="Primary clinical diagnosis (required, non-empty)")
    clinical_notes: Optional[str] = None
    doctor_notes: Optional[str] = None
    follow_up_date: Optional[date] = Field(None, description="Recommended follow-up date, must not be in the past")
    vitals: Optional[VitalsIn] = None
    items: List[PrescribedItemIn] = Field(default_factory=list, description="Prescribed treatments (may be empty)")

    model_config = ConfigDict(from_attributes=True)

    @field_validator("diagnosis")
    @classmethod
    def validate_diagnosis_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Diagnosis must not be empty or whitespace only")
        return v.strip()

    @field_validator("follow_up_date")
    @classmethod
    def validate_follow_up_date_not_past(cls, v: Optional[date]) -> Optional[date]:
        if v is not None and v < date.today():
            raise ValueError("Follow-up date must not be in the past")
        return v
