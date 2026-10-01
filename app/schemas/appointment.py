"""
Pydantic v2 schemas for Appointment, Walk-In, Rescheduling, and Cancellation.
Provides strict validation rules for booking requests and serialization for responses.
"""

from datetime import date, datetime
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field, ConfigDict


class AppointmentType(str, Enum):
    STANDARD = "Standard"
    FOLLOW_UP = "Follow_Up"
    EMERGENCY = "Emergency"
    WALK_IN = "Walk_In"


class AppointmentStatus(str, Enum):
    SCHEDULED = "Scheduled"
    CONFIRMED = "Confirmed"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"
    NO_SHOW = "No_Show"


class AppointmentCreate(BaseModel):
    """Payload for booking a standard scheduled clinic appointment."""
    patient_id: int = Field(..., gt=0, description="Target Patient ID")
    doctor_id: int = Field(..., gt=0, description="Target Doctor ID")
    branch_id: int = Field(..., gt=0, description="Practicing Clinic Branch ID")
    appointment_date: date = Field(..., description="Date of appointment (YYYY-MM-DD)")
    start_time: str = Field(..., description="Start time in HH:MM:SS format")
    duration_minutes: int = Field(default=15, gt=0, le=120, description="Visit duration in minutes (e.g. 15, 30, 45)")
    appointment_type: AppointmentType = Field(default=AppointmentType.STANDARD, description="Category of appointment")
    reason_for_visit: str = Field(..., min_length=2, max_length=255, description="Primary clinical visit reason")
    schedule_id: Optional[int] = Field(default=None, gt=0, description="Optional weekly schedule shift reference")

    model_config = ConfigDict(populate_by_name=True)


class WalkInAppointmentCreate(BaseModel):
    """Fast-path payload for receptionist registering an emergency/unscheduled walk-in."""
    patient_id: int = Field(..., gt=0, description="Target Patient ID")
    doctor_id: int = Field(..., gt=0, description="On-duty Doctor ID")
    branch_id: int = Field(..., gt=0, description="Receiving Branch ID")
    reason_for_visit: str = Field(..., min_length=2, max_length=255, description="Triage reason or clinical complaint")
    duration_minutes: int = Field(default=15, gt=0, le=60, description="Estimated consultation minutes")
    triage_urgency: Optional[str] = Field(default="Normal", description="Urgency level (e.g. Normal, High, Critical)")
    appointment_date: Optional[date] = Field(default=None, description="Optional override date; defaults to today")
    start_time: Optional[str] = Field(default=None, description="Optional override start time (HH:MM:SS); defaults to current time")

    model_config = ConfigDict(populate_by_name=True)


class AppointmentReschedule(BaseModel):
    """Payload to reschedule an existing appointment to a new date and time slot."""
    new_date: date = Field(..., description="New target appointment date")
    new_start_time: str = Field(..., description="New start time in HH:MM:SS format")
    duration_minutes: Optional[int] = Field(default=None, gt=0, le=120, description="Optional updated visit duration")
    reschedule_reason: Optional[str] = Field(default=None, max_length=255, description="Clinical or patient reason for change")

    model_config = ConfigDict(populate_by_name=True)


class AppointmentCancel(BaseModel):
    """Payload for cancelling an appointment with a mandatory audit reason."""
    cancellation_reason: str = Field(..., min_length=3, max_length=255, description="Mandatory reason for cancellation")

    model_config = ConfigDict(populate_by_name=True)


class AppointmentResponse(BaseModel):
    """Standard serialized appointment response returned to frontend client."""
    appointment_id: int = Field(..., alias="Appointment_ID", description="Unique appointment ID")
    patient_id: int = Field(..., alias="Patient_ID", description="Patient ID")
    patient_name: str = Field(..., alias="Patient_Name", description="Patient full name")
    patient_nic: Optional[str] = Field(default=None, alias="Patient_NIC", description="National Identity Card")
    patient_phone: Optional[str] = Field(default=None, alias="Patient_Phone", description="Contact phone number")
    patient_gender: Optional[str] = Field(default=None, alias="Patient_Gender", description="Patient gender")
    doctor_id: int = Field(..., alias="Doctor_ID", description="Doctor ID")
    doctor_name: str = Field(..., alias="Doctor_Name", description="Doctor full name")
    doctor_license: Optional[str] = Field(default=None, alias="Doctor_License", description="SLMC License number")
    branch_id: int = Field(..., alias="Branch_ID", description="Clinic Branch ID")
    branch_name: str = Field(..., alias="Branch_Name", description="Branch name")
    branch_city: Optional[str] = Field(default=None, alias="Branch_City", description="Branch city")
    schedule_id: Optional[int] = Field(default=None, alias="Schedule_ID", description="Shift schedule ID if applicable")
    appointment_date: date = Field(..., alias="Appointment_Date", description="Date of appointment")
    start_time: Any = Field(..., alias="Start_Time", description="Scheduled start time")
    duration_minutes: int = Field(..., alias="Duration_Minutes", description="Duration in minutes")
    end_time: Optional[Any] = Field(default=None, alias="End_Time", description="Calculated end time")
    appointment_type: str = Field(..., alias="Appointment_Type", description="Type of appointment")
    status: str = Field(..., alias="Status", description="Current appointment lifecycle status")
    cancellation_reason: Optional[str] = Field(default=None, alias="Cancellation_Reason", description="Cancellation reason if cancelled")
    reason_for_visit: str = Field(..., alias="Reason_For_Visit", description="Patient visit reason")
    created_at: Optional[datetime] = Field(default=None, alias="Created_At", description="Timestamp record was created")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class AppointmentStatusCountsResponse(BaseModel):
    """Real-time operational summary metrics for receptionist and clinic queue."""
    total: int = Field(..., alias="Total")
    scheduled: int = Field(..., alias="Scheduled")
    confirmed: int = Field(..., alias="Confirmed")
    completed: int = Field(..., alias="Completed")
    cancelled: int = Field(..., alias="Cancelled")
    no_show: int = Field(..., alias="No_Show")
    walk_in: int = Field(..., alias="Walk_In")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)
