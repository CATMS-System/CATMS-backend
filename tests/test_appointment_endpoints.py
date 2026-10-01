"""
Unit and integration tests for Appointment API endpoints (Day 9).
Tests standard booking, collision prevention, walk-in registration,
date/doctor/branch listing, status metrics, and single lookup.
Option C: Plain PyMySQL.
"""

from datetime import date
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.connection import get_db_connection


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="function")
def cleanup_appointments():
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


def test_get_appointment_by_id_success(client):
    """Verifies GET /api/v1/appointments/{id} returns seeded appointment details."""
    response = client.get("/api/v1/appointments/1")
    assert response.status_code == 200
    data = response.json()
    assert data["Appointment_ID"] == 1
    assert data["Patient_ID"] == 1
    assert data["Patient_Name"] == "John Doe"
    assert data["Doctor_ID"] == 1
    assert data["Doctor_Name"] == "Alexander Bennett"
    assert data["Branch_Name"] == "Colombo Main Clinic"
    assert data["Status"] == "Completed"
    assert data["Appointment_Type"] == "Standard"


def test_get_appointment_by_id_not_found(client):
    """Verifies GET /api/v1/appointments/{id} returns 404 for unknown appointment."""
    response = client.get("/api/v1/appointments/999999")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "999999" in data["detail"]


def test_list_appointments_all(client):
    """Verifies GET /api/v1/appointments returns list of appointments."""
    response = client.get("/api/v1/appointments")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 7


def test_list_appointments_filters(client):
    """Verifies query filters by date, doctor, branch, and status."""
    # Filter by date
    res_date = client.get("/api/v1/appointments?date=2026-08-23")
    assert res_date.status_code == 200
    data_date = res_date.json()
    assert len(data_date) >= 3
    assert all(a["Appointment_Date"] == "2026-08-23" for a in data_date)

    # Filter by doctor_id
    res_doc = client.get("/api/v1/appointments?doctor_id=1")
    assert res_doc.status_code == 200
    data_doc = res_doc.json()
    assert all(a["Doctor_ID"] == 1 for a in data_doc)

    # Filter by branch_id
    res_branch = client.get("/api/v1/appointments?branch_id=1")
    assert res_branch.status_code == 200
    data_branch = res_branch.json()
    assert all(a["Branch_ID"] == 1 for a in data_branch)

    # Filter by status
    res_status = client.get("/api/v1/appointments?status=Completed")
    assert res_status.status_code == 200
    data_status = res_status.json()
    assert all(a["Status"] == "Completed" for a in data_status)


def test_get_appointment_status_counts(client):
    """Verifies GET /api/v1/appointments/metrics/status-counts returns operational aggregate metrics."""
    response = client.get("/api/v1/appointments/metrics/status-counts")
    assert response.status_code == 200
    data = response.json()
    assert "Total" in data
    assert "Scheduled" in data
    assert "Confirmed" in data
    assert "Completed" in data
    assert "Cancelled" in data
    assert "No_Show" in data
    assert "Walk_In" in data
    assert data["Total"] >= 7
    assert data["Completed"] > 0


def test_book_standard_appointment_and_collision_conflict(client, cleanup_appointments):
    """
    Verifies standard appointment booking:
    1. Successfully books new appointment (status 201, Scheduled).
    2. Rejects overlapping booking attempt for same doctor with HTTP 409 Conflict.
    """
    booking_payload = {
        "patient_id": 1,
        "doctor_id": 1,
        "branch_id": 1,
        "appointment_date": "2026-11-20",
        "start_time": "10:00:00",
        "duration_minutes": 30,
        "appointment_type": "Standard",
        "reason_for_visit": "Bi-annual cardiac health review",
    }

    # Step 1: Successful booking
    res1 = client.post("/api/v1/appointments", json=booking_payload)
    assert res1.status_code == 201
    appt1 = res1.json()
    assert appt1["Appointment_ID"] > 0
    cleanup_appointments.append(appt1["Appointment_ID"])
    assert appt1["Patient_ID"] == 1
    assert appt1["Doctor_ID"] == 1
    assert appt1["Status"] == "Scheduled"
    assert appt1["Appointment_Type"] == "Standard"
    assert appt1["Appointment_Date"] == "2026-11-20"

    # Step 2: Overlapping booking collision (10:15 - 10:45 overlaps with 10:00 - 10:30)
    conflict_payload = {
        "patient_id": 2,
        "doctor_id": 1,
        "branch_id": 1,
        "appointment_date": "2026-11-20",
        "start_time": "10:15:00",
        "duration_minutes": 30,
        "appointment_type": "Standard",
        "reason_for_visit": "Consultation overlap check",
    }
    res2 = client.post("/api/v1/appointments", json=conflict_payload)
    assert res2.status_code == 409
    detail = res2.json()["detail"]
    assert "overlapping appointment" in detail.lower()


def test_book_appointment_foreign_key_validation(client):
    """Verifies HTTP 400 Bad Request when booking with non-existent patient or doctor."""
    payload_bad_patient = {
        "patient_id": 999999,
        "doctor_id": 1,
        "branch_id": 1,
        "appointment_date": "2026-11-20",
        "start_time": "15:00:00",
        "duration_minutes": 15,
        "appointment_type": "Standard",
        "reason_for_visit": "Checkup",
    }
    res = client.post("/api/v1/appointments", json=payload_bad_patient)
    assert res.status_code == 400
    assert "Patient with ID 999999 does not exist" in res.json()["detail"]


def test_book_walk_in_appointment_success(client, cleanup_appointments):
    """
    Verifies fast-path emergency/walk-in booking:
    Returns status 201 with Appointment_Type='Walk_In', Status='Confirmed', and Schedule_ID=None.
    """
    walk_in_payload = {
        "patient_id": 3,
        "doctor_id": 1,
        "branch_id": 1,
        "reason_for_visit": "Acute severe shortness of breath",
        "duration_minutes": 15,
        "triage_urgency": "Critical",
        "appointment_date": "2026-11-21",
        "start_time": "11:00:00",
    }

    res = client.post("/api/v1/appointments/walk-in", json=walk_in_payload)
    assert res.status_code == 201
    walk_in = res.json()
    assert walk_in["Appointment_ID"] > 0
    cleanup_appointments.append(walk_in["Appointment_ID"])

    assert walk_in["Patient_ID"] == 3
    assert walk_in["Doctor_ID"] == 1
    assert walk_in["Appointment_Type"] == "Walk_In"
    assert walk_in["Status"] == "Confirmed"
    assert walk_in["Schedule_ID"] is None
    assert "[Critical Urgency]" in walk_in["Reason_For_Visit"]


def test_book_appointment_invalid_payload(client):
    """Verifies HTTP 422 Unprocessable Entity for invalid schema payloads."""
    # Negative duration
    payload = {
        "patient_id": 1,
        "doctor_id": 1,
        "branch_id": 1,
        "appointment_date": "2026-11-20",
        "start_time": "10:00:00",
        "duration_minutes": -5,
        "reason_for_visit": "Negative duration test",
    }
    res = client.post("/api/v1/appointments", json=payload)
    assert res.status_code == 422
