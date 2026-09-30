"""
Automated unit test suite for Pydantic v2 schemas for Doctor and Appointment domains.
Verifies request payload validation constraints and response serialization.
"""

import os
import sys
import pytest
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pydantic import ValidationError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.schemas.doctor import (
    SpecialtyResponse,
    DoctorScheduleResponse,
    DoctorListItemResponse,
    DoctorDetailResponse,
)
from app.schemas.appointment import (
    AppointmentType,
    AppointmentStatus,
    AppointmentCreate,
    WalkInAppointmentCreate,
    AppointmentReschedule,
    AppointmentCancel,
    AppointmentResponse,
    AppointmentStatusCountsResponse,
)


def test_appointment_create_valid():
    payload = {
        "patient_id": 1,
        "doctor_id": 1,
        "branch_id": 1,
        "appointment_date": "2026-10-05",
        "start_time": "09:00:00",
        "duration_minutes": 30,
        "appointment_type": "Standard",
        "reason_for_visit": "Cardiology Consultation",
    }
    model = AppointmentCreate(**payload)
    assert model.patient_id == 1
    assert model.appointment_type == AppointmentType.STANDARD
    assert model.appointment_date == date(2026, 10, 5)


def test_appointment_create_invalid_type():
    payload = {
        "patient_id": 1,
        "doctor_id": 1,
        "branch_id": 1,
        "appointment_date": "2026-10-05",
        "start_time": "09:00:00",
        "appointment_type": "InvalidTypeName",
        "reason_for_visit": "Checkup",
    }
    with pytest.raises(ValidationError):
        AppointmentCreate(**payload)


def test_appointment_create_negative_duration():
    payload = {
        "patient_id": 1,
        "doctor_id": 1,
        "branch_id": 1,
        "appointment_date": "2026-10-05",
        "start_time": "09:00:00",
        "duration_minutes": -15,
        "reason_for_visit": "Checkup",
    }
    with pytest.raises(ValidationError):
        AppointmentCreate(**payload)


def test_walk_in_appointment_create_valid():
    payload = {
        "patient_id": 2,
        "doctor_id": 1,
        "branch_id": 1,
        "reason_for_visit": "Acute Chest Pain",
        "triage_urgency": "Critical",
    }
    model = WalkInAppointmentCreate(**payload)
    assert model.patient_id == 2
    assert model.duration_minutes == 15
    assert model.triage_urgency == "Critical"


def test_appointment_cancel_short_reason():
    with pytest.raises(ValidationError):
        AppointmentCancel(cancellation_reason="No")


def test_appointment_cancel_valid():
    model = AppointmentCancel(cancellation_reason="Patient requested reschedule due to travel")
    assert "reschedule" in model.cancellation_reason


def test_appointment_response_serialization():
    raw_db_row = {
        "Appointment_ID": 101,
        "Patient_ID": 1,
        "Patient_Name": "John Doe",
        "Patient_NIC": "852140938V",
        "Patient_Phone": "+94 77 123 4567",
        "Patient_Gender": "Male",
        "Doctor_ID": 1,
        "Doctor_Name": "Alexander Bennett",
        "Doctor_License": "SLMC-88321",
        "Branch_ID": 1,
        "Branch_Name": "Colombo Main Clinic",
        "Branch_City": "Colombo",
        "Schedule_ID": 1,
        "Appointment_Date": date(2026, 10, 5),
        "Start_Time": "09:00:00",
        "Duration_Minutes": 30,
        "End_Time": "09:30:00",
        "Appointment_Type": "Standard",
        "Status": "Scheduled",
        "Cancellation_Reason": None,
        "Reason_For_Visit": "Routine follow-up",
        "Created_At": datetime(2026, 9, 30, 10, 0, 0),
    }
    resp = AppointmentResponse.model_validate(raw_db_row)
    assert resp.appointment_id == 101
    assert resp.patient_name == "John Doe"
    assert resp.doctor_name == "Alexander Bennett"
    dump = resp.model_dump(by_alias=True)
    assert dump["Appointment_ID"] == 101
    assert dump["Status"] == "Scheduled"


def test_doctor_response_serialization():
    raw_doc = {
        "Doctor_ID": 1,
        "Staff_ID": 3,
        "First_Name": "Alexander",
        "Last_Name": "Bennett",
        "Full_Name": "Alexander Bennett",
        "Email": "alexander.bennett@catms.lk",
        "Contact_Number": "+94 77 345 6789",
        "Employment_Status": "Active",
        "Branch_ID": 1,
        "Branch_Name": "Colombo Main Clinic",
        "Branch_City": "Colombo",
        "Branch_Address": "123 Galle Road",
        "License_Number": "SLMC-88321",
        "Standard_Consultation_Fee": Decimal("2500.00"),
        "Specialties": [
            {"Specialty_ID": 1, "Specialty_Name": "Cardiology", "Description": "Heart care"},
            {"Specialty_ID": 2, "Specialty_Name": "General Medicine", "Description": "Primary care"}
        ]
    }
    doc = DoctorDetailResponse.model_validate(raw_doc)
    assert doc.doctor_id == 1
    assert len(doc.specialties) == 2
    assert doc.specialties[0].specialty_name == "Cardiology"


def test_status_counts_response():
    data = {
        "Total": 10,
        "Scheduled": 4,
        "Confirmed": 2,
        "Completed": 3,
        "Cancelled": 1,
        "No_Show": 0,
        "Walk_In": 2,
    }
    resp = AppointmentStatusCountsResponse.model_validate(data)
    assert resp.total == 10
    assert resp.walk_in == 2


if __name__ == "__main__":
    test_appointment_create_valid()
    test_appointment_create_invalid_type()
    test_appointment_create_negative_duration()
    test_walk_in_appointment_create_valid()
    test_appointment_cancel_short_reason()
    test_appointment_cancel_valid()
    test_appointment_response_serialization()
    test_doctor_response_serialization()
    test_status_counts_response()
    print("All Pydantic schema validation tests passed successfully!")
