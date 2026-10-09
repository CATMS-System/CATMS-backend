"""
Clinical Consultation Module Integration Tests.

NOTE: The MySQL database must be seeded before running these tests.
Run `python sql/run_all.py` first to ensure all schema tables, stored procedures,
and seed records exist.
All tests create isolated appointment fixtures to avoid state pollution or seed drift.
"""

import os
import sys
from datetime import date, timedelta
from decimal import Decimal
import pymysql.cursors
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.db.connection import get_db_connection
from app.schemas.consultation import (
    ConsultationCreate,
    ConsultationCreateResponse,
    ConsultationHistoryItem,
    ConsultationOut,
    VitalsIn,
    PrescribedItemIn,
)
from app.api.v1.endpoints.consultations import (
    record_consultation,
    read_consultation,
    read_patient_consultation_history,
)
from app.api.deps import get_current_user
from app.schemas.user import UserAccount, SystemRoleEnum, AccountStatusEnum

client = TestClient(app)


@pytest.fixture(autouse=True)
def auth_override():
    mock_doctor = UserAccount(
        Account_ID=4,
        Username="dr_bennett",
        Password_Hash="",
        System_Role=SystemRoleEnum.Doctor,
        Account_Status=AccountStatusEnum.Active,
    )
    previous = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: mock_doctor
    yield
    if previous is not None:
        app.dependency_overrides[get_current_user] = previous
    else:
        app.dependency_overrides.pop(get_current_user, None)


def create_isolated_appointment(
    patient_id: int = 1,
    doctor_id: int = 1,
    branch_id: int = 1,
    status: str = "Confirmed",
    appt_date: str = "2099-01-01",
    start_time: str = "10:00:00",
    reason: str = "Cardiology evaluation and checkup",
    cancellation_reason: str = None
) -> int:
    """Inserts a dedicated appointment for isolated test execution."""
    if status == "Cancelled" and not cancellation_reason:
        cancellation_reason = "Cancelled for testing"
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO Appointment 
                (Patient_ID, Doctor_ID, Branch_ID, Appointment_Date, Start_Time, Duration_Minutes, Appointment_Type, Status, Cancellation_Reason, Reason_For_Visit)
                VALUES (%s, %s, %s, %s, %s, 20, 'Standard', %s, %s, %s)
                """,
                (patient_id, doctor_id, branch_id, appt_date, start_time, status, cancellation_reason, reason)
            )
            appt_id = cur.lastrowid
            conn.commit()
            return appt_id
    finally:
        conn.close()


def cleanup_isolated_appointment(appt_id: int):
    """Cleans up an isolated appointment and all related consultation and invoice rows."""
    if not appt_id:
        return
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM Invoice WHERE Consultation_ID IN (
                    SELECT Consultation_ID FROM Consultation WHERE Appointment_ID = %s
                )
            """, (appt_id,))
            cur.execute("""
                DELETE FROM Prescribed_Treatment WHERE Consultation_ID IN (
                    SELECT Consultation_ID FROM Consultation WHERE Appointment_ID = %s
                )
            """, (appt_id,))
            cur.execute("DELETE FROM Consultation WHERE Appointment_ID = %s", (appt_id,))
            cur.execute("DELETE FROM Appointment WHERE Appointment_ID = %s", (appt_id,))
            conn.commit()
    finally:
        conn.close()


def test_successful_consultation_creation():
    """
    Verifies that a successful consultation creates Consultation, Prescribed_Treatment items,
    and Invoice, and marks the Appointment as 'Completed'.
    Uses a dedicated isolated appointment and cleans up completely in a finally block.
    """
    target_appt = create_isolated_appointment(
        patient_id=1, doctor_id=1, branch_id=1,
        status="Confirmed", appt_date="2099-01-01", start_time="09:00:00"
    )
    conn = get_db_connection()
    c_id = None
    i_id = None

    try:
        payload = {
            "appointment_id": target_appt,
            "diagnosis": "Cardiovascular Evaluation and Follow-up",
            "clinical_notes": "Patient presents for planned cardiovascular assessment.",
            "doctor_notes": "Advised low-sodium diet and routine aerobic activity.",
            "follow_up_date": (date.today() + timedelta(days=14)).isoformat(),
            "vitals": {
                "bp": "135/85",
                "heart_rate": 78,
                "temperature": 36.8,
                "spo2": 99,
                "weight": 72.0
            },
            "items": [
                {"treatment_id": 1, "quantity": 1, "instructions": "12-Lead ECG resting"},
                {"treatment_id": 2, "quantity": 1, "instructions": "2D Echocardiogram Doppler"}
            ]
        }

        response = client.post("/api/v1/consultations", json=payload)
        status_code, body = response.status_code, response.json()
        assert status_code == 201, f"Expected 201, got {status_code}: {body}"
        assert "consultation_id" in body and body["consultation_id"] is not None
        assert "invoice_id" in body and body["invoice_id"] is not None

        c_id = body["consultation_id"]
        i_id = body["invoice_id"]

        # Advance transaction snapshot under MySQL REPEATABLE READ and verify DB
        conn.commit()
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            # Check appointment status updated to Completed
            cur.execute("SELECT Status FROM Appointment WHERE Appointment_ID = %s", (target_appt,))
            updated_appt = cur.fetchone()
            assert updated_appt["Status"] == "Completed", f"Expected 'Completed', got '{updated_appt['Status']}'"

            # Check Consultation row exists
            cur.execute("SELECT * FROM Consultation WHERE Consultation_ID = %s", (c_id,))
            consultation_row = cur.fetchone()
            assert consultation_row is not None
            assert consultation_row["Appointment_ID"] == target_appt
            assert "Vitals: BP 135/85 mmHg" in consultation_row["Clinical_Notes"]

            # Check Prescribed_Treatment items created
            cur.execute("SELECT * FROM Prescribed_Treatment WHERE Consultation_ID = %s ORDER BY Prescription_Item_ID ASC", (c_id,))
            items = cur.fetchall()
            assert len(items) == 2, f"Expected 2 prescribed items, got {len(items)}"
            assert items[0]["Treatment_ID"] == 1
            assert items[0]["Billed_Unit_Price"] == Decimal("5000.00")
            assert items[1]["Treatment_ID"] == 2
            assert items[1]["Billed_Unit_Price"] == Decimal("12500.00")

            # Check Invoice created with 'Issued' status and attending doctor fee
            cur.execute("SELECT * FROM Invoice WHERE Invoice_ID = %s", (i_id,))
            inv = cur.fetchone()
            assert inv is not None
            assert inv["Invoice_Status"] == "Issued"
            assert inv["Consultation_ID"] == c_id
            assert inv["Billed_Consultation_Fee"] == Decimal("2500.00")

        print("Test Passed: Successful consultation created consultation, items, and invoice, and marked appointment 'Completed'.")
    finally:
        conn.close()
        cleanup_isolated_appointment(target_appt)


def test_invalid_treatment_id_rollback():
    """
    Verifies that an invalid treatment_id raises 422 and rolls everything back.
    Ensures nothing is saved in Consultation, Prescribed_Treatment, or Invoice,
    and appointment status remains unchanged.
    Uses an isolated appointment and cleans up completely in a finally block.
    """
    target_appt = create_isolated_appointment(
        patient_id=1, doctor_id=1, branch_id=1,
        status="Confirmed", appt_date="2099-01-02", start_time="09:00:00"
    )
    conn = get_db_connection()

    try:
        payload = {
            "appointment_id": target_appt,
            "diagnosis": "Rollback Test Diagnosis",
            "items": [
                {"treatment_id": 1, "quantity": 1, "instructions": "Valid ECG"},
                {"treatment_id": 999999, "quantity": 1, "instructions": "Nonexistent treatment"}
            ]
        }

        response = client.post("/api/v1/consultations", json=payload)
        status_code, body = response.status_code, response.json()
        assert status_code == 422, f"Expected 422, got {status_code}: {body}"
        assert "999999" in body.get("detail", "")

        conn.commit()
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            # 1. Appointment status unchanged
            cur.execute("SELECT Status FROM Appointment WHERE Appointment_ID = %s", (target_appt,))
            assert cur.fetchone()["Status"] == "Confirmed"

            # 2. No Consultation created
            cur.execute("SELECT * FROM Consultation WHERE Appointment_ID = %s", (target_appt,))
            assert len(cur.fetchall()) == 0

            # 3. No Prescribed_Treatment created
            cur.execute("""
                SELECT pt.* FROM Prescribed_Treatment pt
                JOIN Consultation c ON pt.Consultation_ID = c.Consultation_ID
                WHERE c.Appointment_ID = %s
            """, (target_appt,))
            assert len(cur.fetchall()) == 0

            # 4. No Invoice created
            cur.execute("""
                SELECT i.* FROM Invoice i
                JOIN Consultation c ON i.Consultation_ID = c.Consultation_ID
                WHERE c.Appointment_ID = %s
            """, (target_appt,))
            assert len(cur.fetchall()) == 0

        print("Test Passed: Invalid treatment_id raised 422 and rolled everything back.")
    finally:
        conn.close()
        cleanup_isolated_appointment(target_appt)


def test_discontinued_treatment_rejected():
    """
    Verifies that attempting to prescribe a discontinued treatment raises 422 and rolls back.
    Uses an isolated appointment and temporary discontinued treatment, cleaning up both in a finally block.
    """
    target_appt = create_isolated_appointment(
        patient_id=4, doctor_id=1, branch_id=1,
        status="Scheduled", appt_date="2099-01-03", start_time="09:00:00"
    )
    conn = get_db_connection()
    temp_disc_id = None

    try:
        # Insert a temporary discontinued treatment
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO Treatment_Catalogue 
                (Category_ID, Service_Code, Treatment_Name, Standard_Unit_Price, Treatment_Status)
                VALUES (1, 'TEST-DISC-ITEM', 'Discontinued Test Panel', 3000.00, 'Discontinued')
                """
            )
            temp_disc_id = cur.lastrowid
            conn.commit()

        payload = {
            "appointment_id": target_appt,
            "diagnosis": "Test Discontinued Item Rejection",
            "items": [
                {"treatment_id": temp_disc_id, "quantity": 1}
            ]
        }

        response = client.post("/api/v1/consultations", json=payload)
        status_code, body = response.status_code, response.json()
        assert status_code == 422, f"Expected 422, got {status_code}: {body}"
        assert "not active" in body.get("detail", "").lower()

        conn.commit()
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SELECT Status FROM Appointment WHERE Appointment_ID = %s", (target_appt,))
            assert cur.fetchone()["Status"] == "Scheduled"

            cur.execute("SELECT * FROM Consultation WHERE Appointment_ID = %s", (target_appt,))
            assert len(cur.fetchall()) == 0

        print("Test Passed: Discontinued treatment rejected with 422 and transaction rolled back.")
    finally:
        try:
            with conn.cursor() as cur:
                if temp_disc_id:
                    cur.execute("DELETE FROM Treatment_Catalogue WHERE Treatment_ID = %s", (temp_disc_id,))
                conn.commit()
        finally:
            conn.close()
            cleanup_isolated_appointment(target_appt)


def test_completed_appointment_returns_409():
    """
    Verifies that attempting to create a consultation for an already Completed appointment returns 409.
    Uses an isolated appointment created directly in Completed status.
    """
    target_appt = create_isolated_appointment(
        patient_id=1, doctor_id=1, branch_id=1,
        status="Completed", appt_date="2099-01-04", start_time="09:00:00"
    )

    try:
        payload = {
            "appointment_id": target_appt,
            "diagnosis": "Consultation on Completed Appointment",
            "items": []
        }

        response = client.post("/api/v1/consultations", json=payload)
        status_code, body = response.status_code, response.json()
        assert status_code == 409, f"Expected 409, got {status_code}: {body}"
        assert "completed" in body.get("detail", "").lower()

        print("Test Passed: Completed appointment returned 409 Conflict.")
    finally:
        cleanup_isolated_appointment(target_appt)


def test_cancelled_appointment_returns_409():
    """
    Verifies that attempting to create a consultation for a Cancelled appointment returns 409.
    Uses an isolated appointment created directly in Cancelled status.
    """
    target_appt = create_isolated_appointment(
        patient_id=1, doctor_id=1, branch_id=1,
        status="Cancelled", appt_date="2099-01-05", start_time="09:00:00"
    )

    try:
        payload = {
            "appointment_id": target_appt,
            "diagnosis": "Consultation on Cancelled Appointment",
            "items": []
        }

        response = client.post("/api/v1/consultations", json=payload)
        status_code, body = response.status_code, response.json()
        assert status_code == 409, f"Expected 409, got {status_code}: {body}"
        assert "cancelled" in body.get("detail", "").lower()

        print("Test Passed: Cancelled appointment returned 409 Conflict.")
    finally:
        cleanup_isolated_appointment(target_appt)


def test_duplicate_consultation_returns_409():
    """
    Verifies that attempting to create a second consultation for the same appointment returns 409.
    Uses an isolated appointment and cleans up completely in a finally block.
    """
    target_appt = create_isolated_appointment(
        patient_id=1, doctor_id=1, branch_id=1,
        status="Confirmed", appt_date="2099-01-06", start_time="09:00:00"
    )
    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            # Insert an initial consultation while appointment remains active
            cur.execute(
                "INSERT INTO Consultation (Appointment_ID, Consultation_Date, Diagnosis) VALUES (%s, CURRENT_DATE, 'Initial Clinical Visit')",
                (target_appt,)
            )
            conn.commit()

        payload = {
            "appointment_id": target_appt,
            "diagnosis": "Duplicate Consultation Attempt",
            "items": []
        }

        response = client.post("/api/v1/consultations", json=payload)
        status_code, body = response.status_code, response.json()
        assert status_code == 409, f"Expected 409, got {status_code}: {body}"
        assert "already exists" in body.get("detail", "").lower()

        print("Test Passed: Duplicate consultation returned 409 Conflict.")
    finally:
        conn.close()
        cleanup_isolated_appointment(target_appt)


def test_patient_history_returns_newest_first():
    """
    Verifies that patient consultation history returns records in strictly newest-first order.
    Uses an isolated appointment for Patient 1 to create a newer consultation record alongside seeded consultation 1,
    confirms descending date ordering, and cleans up completely in a finally block.
    """
    target_appt = create_isolated_appointment(
        patient_id=1, doctor_id=1, branch_id=1,
        status="Confirmed", appt_date="2099-01-07", start_time="09:00:00"
    )
    conn = get_db_connection()
    c_id = None

    try:
        with conn.cursor() as cur:
            # Insert a new consultation for Patient 1 with today's date
            cur.execute(
                """
                INSERT INTO Consultation (Appointment_ID, Consultation_Date, Diagnosis, Clinical_Notes)
                VALUES (%s, CURRENT_DATE, 'Recent Medical Review', 'Vitals: BP 120/80 mmHg. Routine follow-up.')
                """,
                (target_appt,)
            )
            c_id = cur.lastrowid
            conn.commit()

        response = client.get("/api/v1/consultations/patient/1")
        status_code, body = response.status_code, response.json()
        assert status_code == 200, f"Expected 200, got {status_code}: {body}"
        assert isinstance(body, list)
        assert len(body) >= 2, f"Expected at least 2 consultations, got {len(body)}"

        # Verify newest record is first
        assert body[0]["consultation_id"] == c_id
        assert body[0]["consultation_date"] >= body[1]["consultation_date"]

        # Verify entire list is in descending chronological order
        dates = [item["consultation_date"] for item in body]
        assert dates == sorted(dates, reverse=True), "History items not in descending chronological order"

        print(f"Test Passed: Patient history returned {len(body)} records ordered newest first.")
    finally:
        conn.close()
        cleanup_isolated_appointment(target_appt)


def test_unknown_consultation_id_returns_404():
    """Verifies that querying an unknown consultation ID returns 404 Not Found."""
    response = client.get("/api/v1/consultations/999999")
    status_code, body = response.status_code, response.json()
    assert status_code == 404, f"Expected 404, got {status_code}: {body}"
    assert "not found" in body.get("detail", "").lower()
    print("Test Passed: Unknown consultation id returned 404 Not Found.")


def test_get_consultation_by_id_seeded_1():
    """Verifies GET /api/v1/consultations/1 for seeded consultation 1."""
    conn = get_db_connection()
    try:
        model: ConsultationOut = read_consultation(1, conn=conn)
        assert model.consultation_id == 1
        assert model.appointment_id == 1
        assert model.patient_name == "John Doe"
        assert model.doctor_name == "Alexander Bennett"
        assert model.start_time == "09:00"
        assert model.invoice_id == 1
        assert len(model.items) == 2
        assert model.items[0].service_code == "CARD-ECG-01"
        assert model.items[0].line_total == Decimal("5000.00")
        assert model.items[1].service_code == "LAB-LIPID-03"
        assert model.items[1].line_total == Decimal("3500.00")
    finally:
        conn.close()

    response = client.get("/api/v1/consultations/1")
    status_code, body = response.status_code, response.json()
    assert status_code == 200, f"Expected 200, got {status_code}: {body}"
    assert body["consultation_id"] == 1
    assert body["patient_name"] == "John Doe"
    assert body["doctor_name"] == "Alexander Bennett"
    assert body["start_time"] == "09:00"
    assert body["invoice_id"] == 1
    assert len(body["items"]) == 2
    assert Decimal(str(body["items"][0]["line_total"])) == Decimal("5000.00")
    assert Decimal(str(body["items"][1]["line_total"])) == Decimal("3500.00")

    print("Test Passed: GET /api/v1/consultations/1 returned 200 with patient, doctor, '09:00' start_time, items, and line totals.")


def test_get_patient_consultation_history_not_found():
    """Verifies GET /api/v1/consultations/patient/{patient_id} returns 404 for nonexistent patient."""
    response = client.get("/api/v1/consultations/patient/999999")
    status_code, body = response.status_code, response.json()
    assert status_code == 404, f"Expected 404, got {status_code}: {body}"
    assert "not found" in body.get("detail", "").lower()
    print("Test Passed: GET /api/v1/consultations/patient/999999 returned 404 Not Found.")


if __name__ == "__main__":
    print("=" * 70)
    print("Running Consultation Module Tests (Option C: Plain PyMySQL)")
    print("=" * 70)
    test_successful_consultation_creation()
    test_invalid_treatment_id_rollback()
    test_discontinued_treatment_rejected()
    test_completed_appointment_returns_409()
    test_cancelled_appointment_returns_409()
    test_duplicate_consultation_returns_409()
    test_patient_history_returns_newest_first()
    test_unknown_consultation_id_returns_404()
    test_get_consultation_by_id_seeded_1()
    test_get_patient_consultation_history_not_found()
    print("=" * 70)
    print("All consultation tests passed successfully!")
    print("=" * 70)
