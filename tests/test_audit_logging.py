"""
Integration tests for database trigger audit logging:
- Verifies persistent Audit_Log rows are written on Patient and Appointment operations.
- Verifies session variable attribution (@app_account_id, @app_branch_id).
- Verifies audit log API endpoint /api/v1/audit-logs permissions and filtering.
"""

import json
from datetime import date, time
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_user
from app.db.connection import get_db_connection
from app.schemas.user import UserAccount, SystemRoleEnum, AccountStatusEnum


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_admin():
    mock_admin = UserAccount(
        Account_ID=1,
        Username="admin_audit_tester",
        Password_Hash="",
        System_Role=SystemRoleEnum.Admin,
        Account_Status=AccountStatusEnum.Active,
    )
    previous = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: mock_admin
    yield mock_admin
    if previous is not None:
        app.dependency_overrides[get_current_user] = previous
    else:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def auth_receptionist():
    mock_receptionist = UserAccount(
        Account_ID=5,
        Username="nurse_chen_audit",
        Password_Hash="",
        System_Role=SystemRoleEnum.Receptionist,
        Account_Status=AccountStatusEnum.Active,
    )
    previous = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: mock_receptionist
    yield mock_receptionist
    if previous is not None:
        app.dependency_overrides[get_current_user] = previous
    else:
        app.dependency_overrides.pop(get_current_user, None)


def test_patient_insert_and_update_triggers_audit_log(client, auth_admin):
    payload = {
        "first_name": "Audit",
        "last_name": "Person",
        "date_of_birth": "1992-05-10",
        "gender": "Female",
        "nic": "925511223V",
        "contact_number": "+94771239988",
        "email": "audit.person@example.com",
        "street_address": "45 Temple Road",
        "city": "Colombo",
        "state_province": "Western",
        "postal_code": "00300",
        "emergency_contact": {
            "first_name": "Kasun",
            "last_name": "Person",
            "relationship_to_patient": "Brother",
            "contact_number": "+94779876543",
            "street_address": "45 Temple Road",
            "city": "Colombo",
            "postal_code": "00300"
        }
    }
    resp = client.post("/api/v1/patients", json=payload)
    assert resp.status_code == 201, resp.text
    created = resp.json()
    patient_id = created["patient_id"]

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM Audit_Log 
                WHERE Table_Name = 'Patient' AND Record_ID = %s AND Action_Type = 'INSERT'
                ORDER BY Audit_ID DESC LIMIT 1
                """,
                (str(patient_id),)
            )
            insert_log = cur.fetchone()
            assert insert_log is not None, "Expected INSERT audit log row for Patient"
            assert insert_log["Account_ID"] == auth_admin.Account_ID
            new_val = json.loads(insert_log["New_Value"]) if isinstance(insert_log["New_Value"], str) else insert_log["New_Value"]
            assert new_val["first_name"] == "Audit"

        # Update patient
        update_payload = {
            "contact_number": "+94775554433",
            "last_known_updated_at": created["updated_at"]
        }
        update_resp = client.put(f"/api/v1/patients/{patient_id}", json=update_payload)
        assert update_resp.status_code == 200

        conn.commit()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM Audit_Log 
                WHERE Table_Name = 'Patient' AND Record_ID = %s AND Action_Type = 'UPDATE'
                ORDER BY Audit_ID DESC LIMIT 1
                """,
                (str(patient_id),)
            )
            update_log = cur.fetchone()
            assert update_log is not None, "Expected UPDATE audit log row for Patient"
            assert update_log["Account_ID"] == auth_admin.Account_ID
            new_val = json.loads(update_log["New_Value"]) if isinstance(update_log["New_Value"], str) else update_log["New_Value"]
            assert new_val["contact_number"] == "+94775554433"
    finally:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM Audit_Log WHERE Table_Name = 'Patient' AND Record_ID = %s", (str(patient_id),))
            cur.execute("DELETE FROM Emergency_Contact WHERE Patient_ID = %s", (patient_id,))
            cur.execute("DELETE FROM Patient WHERE Patient_ID = %s", (patient_id,))
        conn.commit()
        conn.close()


def test_appointment_insert_and_update_triggers_audit_log():
    conn = get_db_connection()
    appt_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("SET @app_account_id = 6, @app_branch_id = 2")

            cur.execute(
                """
                INSERT INTO Appointment
                (Patient_ID, Doctor_ID, Branch_ID, Appointment_Date, Start_Time, Duration_Minutes, Appointment_Type, Status, Reason_For_Visit)
                VALUES (1, 2, 2, '2026-11-15', '10:00:00', 30, 'Standard', 'Scheduled', 'Routine check')
                """
            )
            appt_id = cur.lastrowid
            conn.commit()

            # Verify INSERT audit log
            cur.execute(
                """
                SELECT * FROM Audit_Log 
                WHERE Table_Name = 'Appointment' AND Record_ID = %s AND Action_Type = 'INSERT'
                ORDER BY Audit_ID DESC LIMIT 1
                """,
                (str(appt_id),)
            )
            insert_log = cur.fetchone()
            assert insert_log is not None, "Expected INSERT audit log row for Appointment"
            assert insert_log["Account_ID"] == 6
            assert insert_log["Branch_ID"] == 2
            new_val = json.loads(insert_log["New_Value"]) if isinstance(insert_log["New_Value"], str) else insert_log["New_Value"]
            assert new_val["Status"] == "Scheduled"

            # Update status
            cur.execute(
                "UPDATE Appointment SET Status = 'Confirmed' WHERE Appointment_ID = %s",
                (appt_id,)
            )
            conn.commit()

            # Verify UPDATE audit log
            cur.execute(
                """
                SELECT * FROM Audit_Log 
                WHERE Table_Name = 'Appointment' AND Record_ID = %s AND Action_Type = 'UPDATE'
                ORDER BY Audit_ID DESC LIMIT 1
                """,
                (str(appt_id),)
            )
            update_log = cur.fetchone()
            assert update_log is not None
            old_val = json.loads(update_log["Old_Value"]) if isinstance(update_log["Old_Value"], str) else update_log["Old_Value"]
            new_val = json.loads(update_log["New_Value"]) if isinstance(update_log["New_Value"], str) else update_log["New_Value"]
            assert old_val["Status"] == "Scheduled"
            assert new_val["Status"] == "Confirmed"

    finally:
        if appt_id:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM Audit_Log WHERE Table_Name = 'Appointment' AND Record_ID = %s", (str(appt_id),))
                cur.execute("DELETE FROM Appointment WHERE Appointment_ID = %s", (appt_id,))
            conn.commit()
        conn.close()


def test_audit_logs_api_admin_can_retrieve_and_filter(client, auth_admin):
    resp = client.get("/api/v1/audit-logs?table_name=Patient&limit=10")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)
    for entry in data:
        assert entry["Table_Name"] == "Patient"
        assert "Action_Type" in entry
        assert "Audit_ID" in entry


def test_audit_logs_api_non_admin_forbidden(client, auth_receptionist):
    resp = client.get("/api/v1/audit-logs")
    assert resp.status_code == 403
    assert "operation not permitted" in resp.json()["detail"].lower()
