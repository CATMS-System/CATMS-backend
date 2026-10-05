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
from app.schemas.consultation import ConsultationCreate, ConsultationCreateResponse, VitalsIn, PrescribedItemIn
from app.api.v1.endpoints.consultations import record_consultation


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


if __name__ == "__main__":
    print("=" * 60)
    print("Running Consultation Module Tests")
    print("=" * 60)
    test_post_consultation_error_mappings()
    test_post_consultation_success_and_cleanup()
    print("=" * 60)
    print("All consultation tests passed successfully!")
    print("=" * 60)
