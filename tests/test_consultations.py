import asyncio
import json
import os
import sys
from datetime import date, timedelta
from decimal import Decimal
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
from app.api.v1.endpoints.consultations import (
    record_consultation,
    read_consultation,
    read_patient_consultation_history,
)


async def _dispatch_asgi(method: str, path: str, json_body: dict = None):
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


def test_post_consultation_success_and_cleanup():
    """Verifies successful POST /api/v1/consultations, HTTP 201, and DB updates."""
    target_appt = 4
    conn = get_db_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SELECT Status FROM Appointment WHERE Appointment_ID = %s", (target_appt,))
            row = cur.fetchone()
            assert row is not None
            orig_status = row["Status"]
            assert orig_status in ("Scheduled", "Confirmed")

        payload = {
            "appointment_id": target_appt,
            "diagnosis": "Cardiology Consultation & Assessment",
            "clinical_notes": "Mild elevated blood pressure observed.",
            "doctor_notes": "Prescribed lifestyle changes and routine tests.",
            "follow_up_date": (date.today() + timedelta(days=14)).isoformat(),
            "vitals": {
                "bp": "135/85",
                "heart_rate": 78,
                "temperature": 36.8,
                "spo2": 99,
                "weight": 72.0
            },
            "items": [
                {"treatment_id": 1, "quantity": 1, "instructions": "Resting ECG"}
            ]
        }

        status_code, body = asyncio.run(_dispatch_asgi("POST", "/api/v1/consultations", payload))
        assert status_code == 201, f"Expected 201, got {status_code}: {body}"
        assert "consultation_id" in body and body["consultation_id"] is not None
        assert "invoice_id" in body and body["invoice_id"] is not None

        c_id = body["consultation_id"]
        i_id = body["invoice_id"]

        # Advance transaction snapshot for repeatable read
        conn.commit()
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            # Check appointment status updated to Completed
            cur.execute("SELECT Status FROM Appointment WHERE Appointment_ID = %s", (target_appt,))
            assert cur.fetchone()["Status"] == "Completed"

            # Check Invoice created with Issued status
            cur.execute("SELECT * FROM Invoice WHERE Invoice_ID = %s", (i_id,))
            inv = cur.fetchone()
            assert inv is not None
            assert inv["Invoice_Status"] == "Issued"
            assert inv["Consultation_ID"] == c_id

        # Clean up
        with conn.cursor() as cur:
            cur.execute("DELETE FROM Invoice WHERE Invoice_ID = %s", (i_id,))
            cur.execute("DELETE FROM Prescribed_Treatment WHERE Consultation_ID = %s", (c_id,))
            cur.execute("DELETE FROM Consultation WHERE Consultation_ID = %s", (c_id,))
            cur.execute("UPDATE Appointment SET Status = %s WHERE Appointment_ID = %s", (orig_status, target_appt))
            conn.commit()

        # Verify restoration
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SELECT Status FROM Appointment WHERE Appointment_ID = %s", (target_appt,))
            assert cur.fetchone()["Status"] == orig_status
            cur.execute("SELECT * FROM Consultation WHERE Appointment_ID = %s", (target_appt,))
            assert len(cur.fetchall()) == 0

        print("Test Passed: POST /api/v1/consultations returned 201 with consultation_id and invoice_id; DB updated and cleaned up.")
    finally:
        conn.close()


def test_post_consultation_error_mappings():
    """Verifies service error mappings: 404 (missing appt), 409 (conflict), 422 (invalid treatment)."""
    # 1. 404 Not Found
    status_code, body = asyncio.run(_dispatch_asgi("POST", "/api/v1/consultations", {
        "appointment_id": 888888,
        "diagnosis": "Nonexistent appointment",
        "items": []
    }))
    assert status_code == 404, f"Expected 404, got {status_code}: {body}"

    # 2. 409 Conflict (Appointment 1 is already 'Completed')
    status_code, body = asyncio.run(_dispatch_asgi("POST", "/api/v1/consultations", {
        "appointment_id": 1,
        "diagnosis": "Conflict appointment",
        "items": []
    }))
    assert status_code == 409, f"Expected 409, got {status_code}: {body}"

    # 3. 422 Unprocessable Entity (Nonexistent treatment item)
    status_code, body = asyncio.run(_dispatch_asgi("POST", "/api/v1/consultations", {
        "appointment_id": 4,
        "diagnosis": "Invalid item appointment",
        "items": [{"treatment_id": 99999, "quantity": 1}]
    }))
    assert status_code == 422, f"Expected 422, got {status_code}: {body}"

    print("Test Passed: Service errors mapped correctly (404, 409, 422).")


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
    # Test via endpoint directly with PyMySQL connection
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

    # Test via full ASGI HTTP request
    status_code, body = asyncio.run(_dispatch_asgi("GET", "/api/v1/consultations/patient/1"))
    assert status_code == 200, f"Expected 200, got {status_code}: {body}"
    assert isinstance(body, list)
    assert len(body) >= 1
    assert body[0]["consultation_id"] == 1
    assert body[0]["consultation_date"] == "2026-08-23"
    assert body[0]["doctor_name"] == "Alexander Bennett"
    assert body[0]["item_count"] == 2
    assert body[0]["follow_up_date"] == "2026-08-26"

    # Verify chronological order (newest first)
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
    print("=" * 60)
    print("Running Consultation Module Tests")
    print("=" * 60)
    test_get_consultation_by_id_seeded_1()
    test_get_consultation_not_found()
    test_get_patient_consultation_history_patient_1()
    test_get_patient_consultation_history_not_found()
    test_post_consultation_error_mappings()
    test_post_consultation_success_and_cleanup()
    print("=" * 60)
    print("All consultation tests passed successfully!")
    print("=" * 60)
