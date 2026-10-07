"""
Pydantic v2 schemas for Doctor and Specialty domain models.
Handles request validation and response serialization for physician profiles,
assigned medical specialties, and weekly branch schedules.
"""

from datetime import date
from decimal import Decimal
from typing import Optional, List, Any
from pydantic import BaseModel, Field, ConfigDict


class SpecialtyBase(BaseModel):
    specialty_name: str = Field(..., alias="Specialty_Name", description="Medical specialty title")
    description: Optional[str] = Field(default=None, alias="Description", description="Description of the specialty")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class SpecialtyResponse(SpecialtyBase):
    specialty_id: int = Field(..., alias="Specialty_ID", description="Unique specialty identifier")
    doctor_count: Optional[int] = Field(default=0, alias="Doctor_Count", description="Number of practicing doctors")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class DoctorScheduleResponse(BaseModel):
    schedule_id: int = Field(..., alias="Schedule_ID", description="Unique schedule identifier")
    doctor_id: int = Field(..., alias="Doctor_ID", description="Doctor identifier")
    branch_id: int = Field(..., alias="Branch_ID", description="Clinic branch identifier")
    branch_name: Optional[str] = Field(default=None, alias="Branch_Name", description="Clinic branch name")
    branch_city: Optional[str] = Field(default=None, alias="Branch_City", description="Branch city")
    day_of_week: str = Field(..., alias="Day_Of_Week", description="Day of the week (Monday-Sunday)")
    start_time: Any = Field(..., alias="Start_Time", description="Shift start time")
    end_time: Any = Field(..., alias="End_Time", description="Shift end time")
    start_time_str: Optional[str] = Field(default=None, alias="Start_Time_Str", description="Formatted start time (HH:MM:SS)")
    end_time_str: Optional[str] = Field(default=None, alias="End_Time_Str", description="Formatted end time (HH:MM:SS)")
    shift_duration_minutes: Optional[int] = Field(default=None, alias="Shift_Duration_Minutes", description="Shift length in minutes")
    availability_status: str = Field(..., alias="Availability_Status", description="Shift status (Active, Suspended, On_Call)")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class DoctorListItemResponse(BaseModel):
    doctor_id: int = Field(..., alias="Doctor_ID", description="Doctor unique ID")
    staff_id: int = Field(..., alias="Staff_ID", description="Associated staff record ID")
    first_name: str = Field(..., alias="First_Name", description="Doctor first name")
    last_name: str = Field(..., alias="Last_Name", description="Doctor last name")
    full_name: str = Field(..., alias="Full_Name", description="Full formatted name")
    email: str = Field(..., alias="Email", description="Professional email address")
    contact_number: str = Field(..., alias="Contact_Number", description="Direct contact phone number")
    employment_status: str = Field(..., alias="Employment_Status", description="Employment status")
    branch_id: int = Field(..., alias="Branch_ID", description="Primary home branch ID")
    branch_name: str = Field(..., alias="Branch_Name", description="Primary home branch name")
    branch_city: Optional[str] = Field(default=None, alias="Branch_City", description="Primary branch city")
    license_number: str = Field(..., alias="License_Number", description="Medical registration license (SLMC)")
    standard_consultation_fee: Decimal = Field(..., alias="Standard_Consultation_Fee", description="Base consultation fee")
    specialties: str = Field(..., alias="Specialties", description="Comma-separated specialty titles")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class DoctorDetailResponse(BaseModel):
    doctor_id: int = Field(..., alias="Doctor_ID")
    staff_id: int = Field(..., alias="Staff_ID")
    first_name: str = Field(..., alias="First_Name")
    last_name: str = Field(..., alias="Last_Name")
    full_name: str = Field(..., alias="Full_Name")
    email: str = Field(..., alias="Email")
    contact_number: str = Field(..., alias="Contact_Number")
    employment_status: str = Field(..., alias="Employment_Status")
    branch_id: int = Field(..., alias="Branch_ID")
    branch_name: str = Field(..., alias="Branch_Name")
    branch_city: Optional[str] = Field(default=None, alias="Branch_City")
    branch_address: Optional[str] = Field(default=None, alias="Branch_Address")
    license_number: str = Field(..., alias="License_Number")
    standard_consultation_fee: Decimal = Field(..., alias="Standard_Consultation_Fee")
    specialties: List[SpecialtyResponse] = Field(default_factory=list, alias="Specialties")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class AvailableSlotResponse(BaseModel):
    start_time: str = Field(..., alias="Start_Time", description="Available slot start time (HH:MM:SS)")
    end_time: str = Field(..., alias="End_Time", description="Available slot end time (HH:MM:SS)")
    duration_minutes: int = Field(..., alias="Duration_Minutes", description="Duration of slot in minutes")
    branch_id: int = Field(..., alias="Branch_ID", description="Clinic branch identifier")
    branch_name: Optional[str] = Field(default=None, alias="Branch_Name", description="Clinic branch name")
    schedule_id: Optional[int] = Field(default=None, alias="Schedule_ID", description="Associated schedule shift ID")
    slot_date: Optional[date] = Field(default=None, alias="Date", description="Target appointment date")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)
