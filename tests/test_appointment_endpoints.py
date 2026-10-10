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
    from app.api.deps import get_current_user
    from app.schemas.user import UserAccount, SystemRoleEnum, AccountStatusEnum
    mock_user = UserAccount(
        Account_ID=1,
        Username="admin_test",
        Password_Hash="",
        System_Role=SystemRoleEnum.Admin,
        Account_Status=AccountStatusEnum.Active,
    )
    previous = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        if previous is not None:
            app.dependency_overrides[get_current_user] = previous
        else:
            app.dependency_overrides.pop(get_current_user, None)


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


def test_reschedule_appointment_success(client, cleanup_appointments):
    """Verifies successfully rescheduling an appointment to a new date and time."""
    # 1. Create appointment
    create_payload = {
        "patient_id": 1,
        "doctor_id": 1,
        "branch_id": 1,
        "appointment_date": "2026-11-25",
        "start_time": "09:00:00",
        "duration_minutes": 30,
        "appointment_type": "Standard",
        "reason_for_visit": "Initial check",
    }
    res_create = client.post("/api/v1/appointments", json=create_payload)
    assert res_create.status_code == 201
    appt_id = res_create.json()["Appointment_ID"]
    cleanup_appointments.append(appt_id)

    # 2. Reschedule to 15:00:00
    reschedule_payload = {
        "new_date": "2026-11-25",
        "new_start_time": "15:00:00",
        "duration_minutes": 30,
        "reschedule_reason": "Patient requested afternoon shift",
    }
    res_resched = client.put(f"/api/v1/appointments/{appt_id}/reschedule", json=reschedule_payload)
    assert res_resched.status_code == 200
    updated = res_resched.json()
    assert updated["Appointment_ID"] == appt_id
    assert updated["Appointment_Date"] == "2026-11-25"
    assert "15:00:00" in str(updated["Start_Time"])
    assert "[Rescheduled: Patient requested afternoon shift]" in updated["Reason_For_Visit"]


def test_reschedule_appointment_collision_conflict(client, cleanup_appointments):
    """Verifies rescheduling rejected with 409 Conflict when target slot collides with an existing booking."""
    # Appointment #1 is on 2026-08-23 at 09:00:00 (Doctor 1, duration 30 mins, 09:00 - 09:30)
    # Book a new appointment on 2026-11-26
    create_payload = {
        "patient_id": 2,
        "doctor_id": 1,
        "branch_id": 1,
        "appointment_date": "2026-11-26",
        "start_time": "11:00:00",
        "duration_minutes": 30,
        "appointment_type": "Standard",
        "reason_for_visit": "Conflict test",
    }
    res_create = client.post("/api/v1/appointments", json=create_payload)
    assert res_create.status_code == 201
    appt_id = res_create.json()["Appointment_ID"]
    cleanup_appointments.append(appt_id)

    # Attempt to reschedule to 2026-08-23 09:15:00 (overlaps with Appt #1 09:00 - 09:30)
    reschedule_payload = {
        "new_date": "2026-08-23",
        "new_start_time": "09:15:00",
        "duration_minutes": 30,
    }
    res_conflict = client.put(f"/api/v1/appointments/{appt_id}/reschedule", json=reschedule_payload)
    assert res_conflict.status_code == 409
    assert "overlapping appointment" in res_conflict.json()["detail"].lower()


def test_reschedule_appointment_not_found(client):
    """Verifies 404 response when attempting to reschedule non-existent appointment."""
    payload = {
        "new_date": "2026-11-25",
        "new_start_time": "15:00:00",
    }
    res = client.put("/api/v1/appointments/999999/reschedule", json=payload)
    assert res.status_code == 404


def test_cancel_appointment_success(client, cleanup_appointments):
    """Verifies cancelling an appointment updates status and stores cancellation reason."""
    create_payload = {
        "patient_id": 1,
        "doctor_id": 1,
        "branch_id": 1,
        "appointment_date": "2026-11-27",
        "start_time": "16:00:00",
        "duration_minutes": 15,
        "appointment_type": "Standard",
        "reason_for_visit": "Cancellation test",
    }
    res_create = client.post("/api/v1/appointments", json=create_payload)
    assert res_create.status_code == 201
    appt_id = res_create.json()["Appointment_ID"]
    cleanup_appointments.append(appt_id)

    # Cancel appointment
    cancel_payload = {
        "cancellation_reason": "Patient called to cancel due to family emergency",
    }
    res_cancel = client.put(f"/api/v1/appointments/{appt_id}/cancel", json=cancel_payload)
    assert res_cancel.status_code == 200
    cancelled = res_cancel.json()
    assert cancelled["Status"] == "Cancelled"
    assert cancelled["Cancellation_Reason"] == "Patient called to cancel due to family emergency"

    # Attempting to cancel again should fail with 400
    res_repeat = client.put(f"/api/v1/appointments/{appt_id}/cancel", json=cancel_payload)
    assert res_repeat.status_code == 400
    assert "already cancelled" in res_repeat.json()["detail"].lower()


def test_cancel_appointment_not_found(client):
    """Verifies 404 response when attempting to cancel non-existent appointment."""
    res = client.put(
        "/api/v1/appointments/999999/cancel",
        json={"cancellation_reason": "Valid reason"}
    )
    assert res.status_code == 404


def test_cancel_appointment_invalid_reason(client):
    """Verifies 422 response when cancellation reason is too short."""
    res = client.put(
        "/api/v1/appointments/1/cancel",
        json={"cancellation_reason": "no"}
    )
    assert res.status_code == 422


def test_get_clinic_queue(client, cleanup_appointments):
    """Verifies live clinic queue retrieves active appointments in chronological sequence."""
    test_date = "2026-11-28"
    # Create two appointments on the same date and branch
    appt1 = client.post("/api/v1/appointments", json={
        "patient_id": 1, "doctor_id": 1, "branch_id": 1,
        "appointment_date": test_date, "start_time": "10:00:00",
        "duration_minutes": 20, "reason_for_visit": "Queue 1"
    }).json()
    cleanup_appointments.append(appt1["Appointment_ID"])

    appt2 = client.post("/api/v1/appointments", json={
        "patient_id": 2, "doctor_id": 1, "branch_id": 1,
        "appointment_date": test_date, "start_time": "10:30:00",
        "duration_minutes": 25, "reason_for_visit": "Queue 2"
    }).json()
    cleanup_appointments.append(appt2["Appointment_ID"])

    # Query queue for branch 1 and test_date
    res_queue = client.get(f"/api/v1/appointments/queue?branch_id=1&date={test_date}")
    assert res_queue.status_code == 200
    queue = res_queue.json()
    assert len(queue) >= 2

    # Verify sequential Queue_Number ordering
    assert queue[0]["Queue_Number"] == 1
    assert queue[0]["Appointment_ID"] == appt1["Appointment_ID"]
    assert queue[0]["Estimated_Wait_Minutes"] == 0

    assert queue[1]["Queue_Number"] == 2
    assert queue[1]["Appointment_ID"] == appt2["Appointment_ID"]
    assert queue[1]["Estimated_Wait_Minutes"] == 20  # Duration of first appointment


def test_patient_cannot_cancel_other_patient_appointment(client):
    """Verifies that a patient cannot cancel another patient's appointment (M3-1)."""
    from app.api.deps import get_current_user
    from app.schemas.user import UserAccount, SystemRoleEnum, AccountStatusEnum
    patient_user = UserAccount(
        Account_ID=11,
        Username="pat_johndoe",
        Password_Hash="",
        System_Role=SystemRoleEnum.Patient,
        Account_Status=AccountStatusEnum.Active,
    )
    previous = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: patient_user
    try:
        # Appointment 5 belongs to Patient 4 (Ananya)
        res = client.put(
            "/api/v1/appointments/5/cancel",
            json={"cancellation_reason": "Unauthorized cancellation attempt"}
        )
        assert res.status_code == 403
        assert "Cannot cancel another patient's appointment" in res.json()["detail"]
    finally:
        if previous:
            app.dependency_overrides[get_current_user] = previous
        else:
            app.dependency_overrides.pop(get_current_user, None)


def test_patient_cannot_reschedule_other_patient_appointment(client):
    """Verifies that a patient cannot reschedule another patient's appointment (M3-1)."""
    from app.api.deps import get_current_user
    from app.schemas.user import UserAccount, SystemRoleEnum, AccountStatusEnum
    patient_user = UserAccount(
        Account_ID=11,
        Username="pat_johndoe",
        Password_Hash="",
        System_Role=SystemRoleEnum.Patient,
        Account_Status=AccountStatusEnum.Active,
    )
    previous = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: patient_user
    try:
        # Appointment 5 belongs to Patient 4
        res = client.put(
            "/api/v1/appointments/5/reschedule",
            json={
                "new_date": "2026-12-01",
                "new_start_time": "15:00:00",
                "duration_minutes": 30,
                "reschedule_reason": "Unauthorized reschedule"
            }
        )
        assert res.status_code == 403
        assert "Cannot reschedule another patient's appointment" in res.json()["detail"]
    finally:
        if previous:
            app.dependency_overrides[get_current_user] = previous
        else:
            app.dependency_overrides.pop(get_current_user, None)


def test_patient_cannot_view_other_patient_appointment(client):
    """Verifies that a patient cannot view details of another patient's appointment (M3-1)."""
    from app.api.deps import get_current_user
    from app.schemas.user import UserAccount, SystemRoleEnum, AccountStatusEnum
    patient_user = UserAccount(
        Account_ID=11,
        Username="pat_johndoe",
        Password_Hash="",
        System_Role=SystemRoleEnum.Patient,
        Account_Status=AccountStatusEnum.Active,
    )
    previous = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: patient_user
    try:
        # Appointment 5 belongs to Patient 4
        res = client.get("/api/v1/appointments/5")
        assert res.status_code == 403
        assert "Cannot view another patient's appointment" in res.json()["detail"]
    finally:
        if previous:
            app.dependency_overrides[get_current_user] = previous
        else:
            app.dependency_overrides.pop(get_current_user, None)


def test_patient_cannot_book_for_other_patient(client):
    """Verifies that a patient cannot book an appointment with another patient's ID (M3-1)."""
    from app.api.deps import get_current_user
    from app.schemas.user import UserAccount, SystemRoleEnum, AccountStatusEnum
    patient_user = UserAccount(
        Account_ID=11,
        Username="pat_johndoe",
        Password_Hash="",
        System_Role=SystemRoleEnum.Patient,
        Account_Status=AccountStatusEnum.Active,
    )
    previous = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: patient_user
    try:
        res = client.post("/api/v1/appointments", json={
            "patient_id": 4,  # Trying to book for patient 4 while logged in as patient 1
            "doctor_id": 1,
            "branch_id": 1,
            "appointment_date": "2026-12-15",
            "start_time": "09:00:00",
            "duration_minutes": 15,
            "appointment_type": "Standard",
            "reason_for_visit": "Unauthorized booking"
        })
        assert res.status_code == 403
        assert "Patients can only book appointments for themselves" in res.json()["detail"]
    finally:
        if previous:
            app.dependency_overrides[get_current_user] = previous
        else:
            app.dependency_overrides.pop(get_current_user, None)


def test_patient_list_appointments_returns_only_own_appointments(client):
    """Verifies that a patient listing appointments only receives their own records (M3-2)."""
    from app.api.deps import get_current_user
    from app.schemas.user import UserAccount, SystemRoleEnum, AccountStatusEnum
    patient_user = UserAccount(
        Account_ID=11,
        Username="pat_johndoe",
        Password_Hash="",
        System_Role=SystemRoleEnum.Patient,
        Account_Status=AccountStatusEnum.Active,
    )
    previous = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: patient_user
    try:
        res = client.get("/api/v1/appointments")
        assert res.status_code == 200
        records = res.json()
        assert len(records) > 0
        for item in records:
            assert item["Patient_ID"] == 1
            assert item["Patient_Name"] == "John Doe"
    finally:
        if previous:
            app.dependency_overrides[get_current_user] = previous
        else:
            app.dependency_overrides.pop(get_current_user, None)


def test_patient_can_cancel_own_appointment(client, cleanup_appointments):
    """Verifies that a patient can successfully cancel their own appointment (M3-1)."""
    from app.api.deps import get_current_user
    from app.schemas.user import UserAccount, SystemRoleEnum, AccountStatusEnum
    patient_user = UserAccount(
        Account_ID=11,
        Username="pat_johndoe",
        Password_Hash="",
        System_Role=SystemRoleEnum.Patient,
        Account_Status=AccountStatusEnum.Active,
    )
    previous = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: patient_user
    try:
        # Book a legitimate appointment for patient 1
        book_res = client.post("/api/v1/appointments", json={
            "patient_id": 1,
            "doctor_id": 1,
            "branch_id": 1,
            "appointment_date": "2026-12-20",
            "start_time": "10:00:00",
            "duration_minutes": 20,
            "appointment_type": "Standard",
            "reason_for_visit": "Own appointment test"
        })
        assert book_res.status_code == 201
        created_appt = book_res.json()
        cleanup_appointments.append(created_appt["Appointment_ID"])

        # Cancel own appointment
        cancel_res = client.put(
            f"/api/v1/appointments/{created_appt['Appointment_ID']}/cancel",
            json={"cancellation_reason": "Patient decided to cancel"}
        )
        assert cancel_res.status_code == 200
        assert cancel_res.json()["Status"] == "Cancelled"
    finally:
        if previous:
            app.dependency_overrides[get_current_user] = previous
        else:
            app.dependency_overrides.pop(get_current_user, None)


def test_staff_list_appointments_scoped_to_branch(client):
    """Verifies that Receptionist appointments listing is scoped to their branch (M3-2)."""
    from app.api.deps import get_current_user
    from app.schemas.user import UserAccount, SystemRoleEnum, AccountStatusEnum
    # Nurse Chen has Account_ID=5 and is assigned to Branch 1
    receptionist_user = UserAccount(
        Account_ID=5,
        Username="nurse_chen",
        Password_Hash="",
        System_Role=SystemRoleEnum.Receptionist,
        Account_Status=AccountStatusEnum.Active,
    )
    previous = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: receptionist_user
    try:
        res = client.get("/api/v1/appointments")
        assert res.status_code == 200
        records = res.json()
        assert len(records) > 0
        for item in records:
            assert item["Branch_ID"] == 1
    finally:
        if previous:
            app.dependency_overrides[get_current_user] = previous
        else:
            app.dependency_overrides.pop(get_current_user, None)


