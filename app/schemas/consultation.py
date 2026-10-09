"""
Pydantic schemas for Clinical Consultations domain (Member 4).
Includes request and response models for recording clinical notes, patient vitals,
prescribing itemized treatments, and querying consultation history.
"""

from datetime import date
from decimal import Decimal
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ==============================================================================
# Request Schemas
# ==============================================================================

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


# ==============================================================================
# Response Schemas
# ==============================================================================

class ConsultationCreateResponse(BaseModel):
    """Response returned upon successful consultation creation."""
    consultation_id: int
    invoice_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class PrescribedItemOut(BaseModel):
    """Serialized prescribed treatment item returned from consultation query."""
    prescription_item_id: int
    treatment_id: int
    service_code: str
    treatment_name: str
    quantity: int
    billed_unit_price: Decimal
    line_total: Optional[Decimal] = None
    instructions: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def compute_line_total(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if data.get("line_total") is None and data.get("Line_Total") is None:
                qty = data.get("quantity", data.get("Quantity"))
                price = data.get("billed_unit_price", data.get("Billed_Unit_Price"))
                if qty is not None and price is not None:
                    data["line_total"] = Decimal(str(qty)) * Decimal(str(price))
        return data


class ConsultationOut(BaseModel):
    """Detailed consultation response with patient/doctor details, items, and billing link."""
    consultation_id: int
    appointment_id: int
    consultation_date: date
    diagnosis: str
    clinical_notes: Optional[str] = None
    doctor_notes: Optional[str] = None
    follow_up_date: Optional[date] = None
    patient_name: str
    doctor_name: str
    appointment_date: Optional[date] = None
    start_time: Optional[str] = None
    vitals: Optional[VitalsIn] = None
    items: List[PrescribedItemOut] = Field(default_factory=list)
    invoice_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ConsultationHistoryItem(BaseModel):
    """Compact consultation history card for patient medical timeline."""
    consultation_id: int
    consultation_date: date
    diagnosis: str
    doctor_name: str
    follow_up_date: Optional[date] = None
    item_count: int = 0

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
