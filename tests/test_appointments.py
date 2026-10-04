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
from app.services.appointment_service import book_appointment_atomic


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
