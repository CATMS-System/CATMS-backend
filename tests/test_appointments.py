"""
Automated unit and integration test suite for Appointment lifecycle,
conflict prevention, walk-in triage, and queue management (Day 11).
Option C: Plain PyMySQL + FastAPI TestClient.
"""

from datetime import date
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.connection import get_db_connection
from app.services.appointment_service import (
    book_appointment_atomic,
    AppointmentConflictError,
)



@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="function")
def db_conn():
    conn = get_db_connection()
    yield conn
    conn.close()


@pytest.fixture(scope="function")
def cleanup_records():
    """Tracks created appointment IDs and cleans them up after each test."""
    created_ids = []
    yield created_ids
    if created_ids:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                format_strings = ",".join(["%s"] * len(created_ids))
                cur.execute(f"DELETE FROM Appointment WHERE Appointment_ID IN ({format_strings})", tuple(created_ids))
            conn.commit()
        finally:
            conn.close()


# ============================================================================
# Task 1: Standard Appointment Booking
# ============================================================================

def test_case_1_standard_appointment_booking_service(db_conn, cleanup_records):
    """
    Day 11 - Test Case 1 (Service Layer):
    Verifies book_appointment_atomic creates a standard appointment record
    with atomic commit, correct initial status 'Scheduled', and joined relations.
    """
    test_date = date(2026, 12, 1)
    test_time = "10:00:00"

    appt = book_appointment_atomic(
        conn=db_conn,
        patient_id=1,
        doctor_id=1,
        branch_id=1,
        appointment_date=test_date,
        start_time=test_time,
        duration_minutes=30,
        appointment_type="Standard",
        reason_for_visit="Routine cardiological checkup",
        schedule_id=1,
    )

    assert appt is not None
    assert appt["Appointment_ID"] > 0
    cleanup_records.append(appt["Appointment_ID"])

    assert appt["Patient_ID"] == 1
    assert appt["Patient_Name"] == "John Doe"
    assert appt["Doctor_ID"] == 1
    assert appt["Doctor_Name"] == "Alexander Bennett"
    assert appt["Branch_ID"] == 1
    assert appt["Branch_Name"] == "Colombo Main Clinic"
    assert appt["Status"] == "Scheduled"
    assert appt["Appointment_Type"] == "Standard"
    assert appt["Duration_Minutes"] == 30
    assert appt["Schedule_ID"] == 1


def test_case_1_standard_appointment_booking_api(client, cleanup_records):
    """
    Day 11 - Test Case 1 (API Layer):
    Verifies POST /api/v1/appointments returns HTTP 201 Created
    with serialized appointment payload.
    """
    payload = {
        "patient_id": 2,
        "doctor_id": 1,
        "branch_id": 1,
        "appointment_date": "2026-12-01",
        "start_time": "11:00:00",
        "duration_minutes": 30,
        "appointment_type": "Standard",
        "reason_for_visit": "Hypertension consultation",
    }
    response = client.post("/api/v1/appointments", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["Appointment_ID"] > 0
    cleanup_records.append(data["Appointment_ID"])
    assert data["Status"] == "Scheduled"
    assert data["Doctor_Name"] == "Alexander Bennett"
    assert "11:00:00" in str(data["Start_Time"])


# ============================================================================
# Task 2: Overlapping Appointment Booking Conflict (HTTP 409)
# ============================================================================

def test_case_2_overlapping_appointment_booking_service(db_conn, cleanup_records):
    """
    Day 11 - Test Case 2 (Service Layer):
    Verifies that attempting to book an overlapping slot raises AppointmentConflictError.
    Tests partial overlap: candidate [14:15, 14:45] vs existing [14:00, 14:30].
    """
    test_date = date(2026, 12, 2)
    initial = book_appointment_atomic(
        conn=db_conn,
        patient_id=1,
        doctor_id=1,
        branch_id=1,
        appointment_date=test_date,
        start_time="14:00:00",
        duration_minutes=30,
        appointment_type="Standard",
        reason_for_visit="First visit",
    )
    cleanup_records.append(initial["Appointment_ID"])

    with pytest.raises(AppointmentConflictError) as exc_info:
        book_appointment_atomic(
            conn=db_conn,
            patient_id=2,
            doctor_id=1,
            branch_id=1,
            appointment_date=test_date,
            start_time="14:15:00",
            duration_minutes=30,
            appointment_type="Standard",
            reason_for_visit="Conflicting visit",
        )
    assert "overlapping appointment" in str(exc_info.value).lower()


def test_case_2_overlapping_appointment_booking_api(client, cleanup_records):
    """
    Day 11 - Test Case 2 (API Layer):
    Verifies POST /api/v1/appointments returns HTTP 409 Conflict
    when slot is already booked for the same doctor.
    """
    test_date = "2026-12-03"
    res1 = client.post("/api/v1/appointments", json={
        "patient_id": 1,
        "doctor_id": 1,
        "branch_id": 1,
        "appointment_date": test_date,
        "start_time": "09:00:00",
        "duration_minutes": 30,
        "appointment_type": "Standard",
        "reason_for_visit": "Seeded booking",
    })
    assert res1.status_code == 201
    cleanup_records.append(res1.json()["Appointment_ID"])

    res2 = client.post("/api/v1/appointments", json={
        "patient_id": 2,
        "doctor_id": 1,
        "branch_id": 1,
        "appointment_date": test_date,
        "start_time": "09:20:00",
        "duration_minutes": 30,
        "appointment_type": "Standard",
        "reason_for_visit": "Colliding booking",
    })
    assert res2.status_code == 409
    assert "overlapping appointment" in res2.json()["detail"].lower()


def test_adjacent_slots_do_not_collide(db_conn, cleanup_records):
    """
    Verifies back-to-back adjacent slots (e.g. 10:00-10:30 and 10:30-11:00)
    do NOT trigger collision error.
    """
    test_date = date(2026, 12, 4)
    appt1 = book_appointment_atomic(
        conn=db_conn,
        patient_id=1,
        doctor_id=1,
        branch_id=1,
        appointment_date=test_date,
        start_time="10:00:00",
        duration_minutes=30,
        appointment_type="Standard",
        reason_for_visit="First slot",
    )
    cleanup_records.append(appt1["Appointment_ID"])

    appt2 = book_appointment_atomic(
        conn=db_conn,
        patient_id=2,
        doctor_id=1,
        branch_id=1,
        appointment_date=test_date,
        start_time="10:30:00",
        duration_minutes=30,
        appointment_type="Standard",
        reason_for_visit="Adjacent slot",
    )
    cleanup_records.append(appt2["Appointment_ID"])
    assert appt2["Appointment_ID"] > 0


# ============================================================================
# Task 3: Emergency Walk-In Booking
# ============================================================================

def test_case_3_emergency_walk_in_booking_service(db_conn, cleanup_records):
    """
    Day 11 - Test Case 3 (Service Layer):
    Verifies walk-in creation succeeds with null schedule (Schedule_ID = None),
    Appointment_Type = 'Walk_In', and immediate Status = 'Confirmed'.
    """
    test_date = date(2026, 12, 5)
    walk_in = book_appointment_atomic(
        conn=db_conn,
        patient_id=3,
        doctor_id=1,
        branch_id=1,
        appointment_date=test_date,
        start_time="15:30:00",
        duration_minutes=15,
        appointment_type="Walk_In",
        reason_for_visit="[Critical Urgency] Severe dizziness and collapse",
        schedule_id=None,
    )

    assert walk_in is not None
    assert walk_in["Appointment_ID"] > 0
    cleanup_records.append(walk_in["Appointment_ID"])

    assert walk_in["Appointment_Type"] == "Walk_In"
    assert walk_in["Status"] == "Confirmed"
    assert walk_in["Schedule_ID"] is None
    assert "[Critical Urgency]" in walk_in["Reason_For_Visit"]


def test_case_3_emergency_walk_in_booking_api(client, cleanup_records):
    """
    Day 11 - Test Case 3 (API Layer):
    Verifies POST /api/v1/appointments/walk-in succeeds with 201 Created,
    populating triage urgency badge, Schedule_ID=None, and Status=Confirmed.
    """
    payload = {
        "patient_id": 4,
        "doctor_id": 1,
        "branch_id": 1,
        "reason_for_visit": "High fever and dehydration",
        "duration_minutes": 20,
        "triage_urgency": "High",
        "appointment_date": "2026-12-05",
        "start_time": "16:00:00",
    }
    res = client.post("/api/v1/appointments/walk-in", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["Appointment_ID"] > 0
    cleanup_records.append(data["Appointment_ID"])

    assert data["Appointment_Type"] == "Walk_In"
    assert data["Status"] == "Confirmed"
    assert data["Schedule_ID"] is None
    assert "[High Urgency]" in data["Reason_For_Visit"]


