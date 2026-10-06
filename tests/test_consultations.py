import asyncio
import json
import os
import sys
from datetime import date, timedelta
from decimal import Decimal
from fastapi import HTTPException
import pymysql.cursors

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
from app.services.consultation_service import create_consultation
from app.api.v1.endpoints.consultations import (
    record_consultation,
    read_consultation,
    read_patient_consultation_history,
)


async def _dispatch_asgi(method: str, path: str, json_body: dict = None):
    """Dispatches a request through the FastAPI ASGI application pipeline."""
    body_bytes = json.dumps(json_body).encode("utf-8") if json_body is not None else b""
    headers = [
        [b"host", b"testserver"],
        [b"content-type", b"application/json"],
        [b"content-length", str(len(body_bytes)).encode("ascii")],
    ]
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": headers,
    }
    response_body = []
    response_status = None

    async def receive():
        return {"type": "http.request", "body": body_bytes, "more_body": False}

    async def send(message):
        nonlocal response_status
        if message["type"] == "http.response.start":
            response_status = message["status"]
        elif message["type"] == "http.response.body":
            response_body.append(message.get("body", b""))

    await app(scope, receive, send)
    raw_text = b"".join(response_body).decode("utf-8")
    try:
        parsed = json.loads(raw_text) if raw_text else {}
    except Exception:
        parsed = {"raw": raw_text}
    return response_status, parsed


def test_successful_consultation_creation():
    """
    Verifies that a successful consultation creates Consultation, Prescribed_Treatment items,
    and Invoice, and marks the Appointment as 'Completed'.
    Uses appointment 4, with status restoration and deletion of created rows in a finally block.
    """
    target_appt = 4
    conn = get_db_connection()
    c_id = None
    i_id = None
    orig_status = None

    try:
        # 1. Fetch and verify initial appointment status
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SELECT Status FROM Appointment WHERE Appointment_ID = %s", (target_appt,))
            appt_row = cur.fetchone()
            assert appt_row is not None, f"Appointment {target_appt} not found"
            orig_status = appt_row["Status"]
            assert orig_status in ("Scheduled", "Confirmed"), f"Invalid initial status: {orig_status}"

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

        # 2. Invoke endpoint
        status_code, body = asyncio.run(_dispatch_asgi("POST", "/api/v1/consultations", payload))
        assert status_code == 201, f"Expected 201, got {status_code}: {body}"
        assert "consultation_id" in body and body["consultation_id"] is not None
        assert "invoice_id" in body and body["invoice_id"] is not None

        c_id = body["consultation_id"]
        i_id = body["invoice_id"]

        # 3. Advance transaction snapshot under MySQL REPEATABLE READ and verify DB
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
        # 4. Clean up in finally block: delete created rows and restore appointment status
        try:
            with conn.cursor() as cur:
                if i_id:
                    cur.execute("DELETE FROM Invoice WHERE Invoice_ID = %s", (i_id,))
                if c_id:
                    cur.execute("DELETE FROM Prescribed_Treatment WHERE Consultation_ID = %s", (c_id,))
                    cur.execute("DELETE FROM Consultation WHERE Consultation_ID = %s", (c_id,))
                if orig_status:
                    cur.execute("UPDATE Appointment SET Status = %s WHERE Appointment_ID = %s", (orig_status, target_appt))
                conn.commit()
        finally:
            conn.close()


def test_invalid_treatment_id_rollback():
    """
    Verifies that an invalid treatment_id raises 422 and rolls everything back.
    Ensures nothing is saved in Consultation, Prescribed_Treatment, or Invoice,
    and appointment status remains unchanged.
    Uses appointment 4, with status restoration and cleanup in a finally block.
    """
    target_appt = 4
    conn = get_db_connection()
    orig_status = None
    created_c_id = None

    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SELECT Status FROM Appointment WHERE Appointment_ID = %s", (target_appt,))
            appt_row = cur.fetchone()
            assert appt_row is not None
            orig_status = appt_row["Status"]
            assert orig_status in ("Scheduled", "Confirmed")

        # Payload includes one valid item and one non-existent treatment_id
        payload = {
            "appointment_id": target_appt,
            "diagnosis": "Rollback Test Diagnosis",
            "items": [
                {"treatment_id": 1, "quantity": 1, "instructions": "Valid ECG"},
                {"treatment_id": 999999, "quantity": 1, "instructions": "Nonexistent treatment"}
            ]
        }

        status_code, body = asyncio.run(_dispatch_asgi("POST", "/api/v1/consultations", payload))
        assert status_code == 422, f"Expected 422, got {status_code}: {body}"
        assert "999999" in body.get("detail", "")

        # Verify atomic rollback: no rows created and appointment status untouched
        conn.commit()
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            # 1. Appointment status unchanged
            cur.execute("SELECT Status FROM Appointment WHERE Appointment_ID = %s", (target_appt,))
            assert cur.fetchone()["Status"] == orig_status

            # 2. No Consultation created
            cur.execute("SELECT * FROM Consultation WHERE Appointment_ID = %s", (target_appt,))
            consultations = cur.fetchall()
            assert len(consultations) == 0, f"Expected 0 consultations after rollback, found: {consultations}"

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
        try:
            with conn.cursor() as cur:
                # Safety cleanup in case of partial commit
                cur.execute("""
                    DELETE FROM Invoice WHERE Consultation_ID IN (
                        SELECT Consultation_ID FROM Consultation WHERE Appointment_ID = %s
                    )
                """, (target_appt,))
                cur.execute("""
                    DELETE FROM Prescribed_Treatment WHERE Consultation_ID IN (
                        SELECT Consultation_ID FROM Consultation WHERE Appointment_ID = %s
                    )
                """, (target_appt,))
                cur.execute("DELETE FROM Consultation WHERE Appointment_ID = %s", (target_appt,))
                if orig_status:
                    cur.execute("UPDATE Appointment SET Status = %s WHERE Appointment_ID = %s", (orig_status, target_appt))
                conn.commit()
        finally:
            conn.close()


def test_discontinued_treatment_rejected():
    """
    Verifies that attempting to prescribe a discontinued treatment raises 422 and rolls back.
    Uses appointment 5, inserts a temporary discontinued treatment, and restores status
    and deletes created rows in a finally block.
    """
    target_appt = 5
    conn = get_db_connection()
    orig_status = None
    temp_disc_id = None

    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SELECT Status FROM Appointment WHERE Appointment_ID = %s", (target_appt,))
            appt_row = cur.fetchone()
            assert appt_row is not None
            orig_status = appt_row["Status"]
            assert orig_status in ("Scheduled", "Confirmed")

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

        # Payload prescribing the discontinued treatment
        payload = {
            "appointment_id": target_appt,
            "diagnosis": "Test Discontinued Item Rejection",
            "items": [
                {"treatment_id": temp_disc_id, "quantity": 1}
            ]
        }

        status_code, body = asyncio.run(_dispatch_asgi("POST", "/api/v1/consultations", payload))
        assert status_code == 422, f"Expected 422, got {status_code}: {body}"
        assert "not active" in body.get("detail", "").lower()

        # Verify rollback: no rows created for Appointment 5
        conn.commit()
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SELECT Status FROM Appointment WHERE Appointment_ID = %s", (target_appt,))
            assert cur.fetchone()["Status"] == orig_status

            cur.execute("SELECT * FROM Consultation WHERE Appointment_ID = %s", (target_appt,))
            assert len(cur.fetchall()) == 0

        print("Test Passed: Discontinued treatment rejected with 422 and transaction rolled back.")
    finally:
        try:
            with conn.cursor() as cur:
                # Remove temporary discontinued item
                if temp_disc_id:
                    cur.execute("DELETE FROM Treatment_Catalogue WHERE Treatment_ID = %s", (temp_disc_id,))
                # Safety cleanup for appointment 5
                cur.execute("""
                    DELETE FROM Invoice WHERE Consultation_ID IN (
                        SELECT Consultation_ID FROM Consultation WHERE Appointment_ID = %s
                    )
                """, (target_appt,))
                cur.execute("""
                    DELETE FROM Prescribed_Treatment WHERE Consultation_ID IN (
                        SELECT Consultation_ID FROM Consultation WHERE Appointment_ID = %s
                    )
                """, (target_appt,))
                cur.execute("DELETE FROM Consultation WHERE Appointment_ID = %s", (target_appt,))
                if orig_status:
                    cur.execute("UPDATE Appointment SET Status = %s WHERE Appointment_ID = %s", (orig_status, target_appt))
                conn.commit()
        finally:
            conn.close()


def test_get_consultation_by_id_seeded_1():
    """Verifies GET /api/v1/consultations/1 for seeded consultation 1."""
    # Test via endpoint directly with PyMySQL connection
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

    # Test via full ASGI HTTP request
    status_code, body = asyncio.run(_dispatch_asgi("GET", "/api/v1/consultations/1"))
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


def test_get_consultation_not_found():
    """Verifies GET /api/v1/consultations/{consultation_id} returns 404 for nonexistent id."""
    status_code, body = asyncio.run(_dispatch_asgi("GET", "/api/v1/consultations/999999"))
    assert status_code == 404, f"Expected 404, got {status_code}: {body}"
    assert "not found" in body.get("detail", "").lower()
    print("Test Passed: GET /api/v1/consultations/999999 returned 404 Not Found.")


def test_get_patient_consultation_history_patient_1():
    """Verifies GET /api/v1/consultations/patient/1 returns chronological history with item_count."""
    conn = get_db_connection()
    try:
        models = read_patient_consultation_history(1, conn=conn)
        assert len(models) >= 1
        first_item: ConsultationHistoryItem = models[0]
        assert first_item.consultation_id == 1
        assert first_item.consultation_date == date(2026, 8, 23)
        assert first_item.doctor_name == "Alexander Bennett"
        assert first_item.item_count == 2
        assert first_item.follow_up_date == date(2026, 8, 26)
    finally:
        conn.close()

    status_code, body = asyncio.run(_dispatch_asgi("GET", "/api/v1/consultations/patient/1"))
    assert status_code == 200, f"Expected 200, got {status_code}: {body}"
    assert isinstance(body, list)
    assert len(body) >= 1
    assert body[0]["consultation_id"] == 1
    assert body[0]["consultation_date"] == "2026-08-23"
    assert body[0]["doctor_name"] == "Alexander Bennett"
    assert body[0]["item_count"] == 2
    assert body[0]["follow_up_date"] == "2026-08-26"

    dates = [item["consultation_date"] for item in body]
    assert dates == sorted(dates, reverse=True), "History items not in descending chronological order"

    print("Test Passed: GET /api/v1/consultations/patient/1 returned chronological history list with item_count.")


def test_get_patient_consultation_history_not_found():
    """Verifies GET /api/v1/consultations/patient/{patient_id} returns 404 for nonexistent patient."""
    status_code, body = asyncio.run(_dispatch_asgi("GET", "/api/v1/consultations/patient/999999"))
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
    test_get_consultation_by_id_seeded_1()
    test_get_consultation_not_found()
    test_get_patient_consultation_history_patient_1()
    test_get_patient_consultation_history_not_found()
    print("=" * 70)
    print("All consultation tests passed successfully!")
    print("=" * 70)
