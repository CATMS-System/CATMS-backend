# a doctor can only record consultations for their own appointments,
# and an unknown appointment id is never redirected to another appointment
import pytest
from fastapi.testclient import TestClient

from app.main import app


def doctor_headers(client, username):
    response = client.post(
        "/api/v1/auth/login", data={"username": username, "password": "Password123!"}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


# a confirmed appointment for dr_bennett (doctor 1), deleted when the test ends
@pytest.fixture
def bennett_appointment(db):
    with db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO Appointment (Patient_ID, Doctor_ID, Branch_ID, Appointment_Date, "
            "Start_Time, Duration_Minutes, Appointment_Type, Status, Reason_For_Visit) "
            "VALUES (1, 1, 1, '2099-02-02', '11:00:00', 15, 'Standard', 'Confirmed', "
            "'ownership test')"
        )
        appointment_id = cursor.lastrowid
    db.commit()
    yield appointment_id
    with db.cursor() as cursor:
        cursor.execute(
            "DELETE FROM Invoice WHERE Consultation_ID IN "
            "(SELECT Consultation_ID FROM Consultation WHERE Appointment_ID = %s)",
            (appointment_id,),
        )
        cursor.execute("DELETE FROM Consultation WHERE Appointment_ID = %s", (appointment_id,))
        cursor.execute("DELETE FROM Appointment WHERE Appointment_ID = %s", (appointment_id,))
    db.commit()


def consultation(appointment_id):
    return {"appointment_id": appointment_id, "diagnosis": "ownership test", "items": []}


def test_other_doctor_cannot_record_consultation(db, bennett_appointment):
    client = TestClient(app)
    headers = doctor_headers(client, "dr_jenkins")

    response = client.post("/api/v1/consultations", json=consultation(bennett_appointment), headers=headers)
    assert response.status_code == 403, response.text

    with db.cursor() as cursor:
        cursor.execute("SELECT Status FROM Appointment WHERE Appointment_ID = %s", (bennett_appointment,))
        assert cursor.fetchone()["Status"] == "Confirmed"


def test_unknown_appointment_returns_404(db):
    client = TestClient(app)
    headers = doctor_headers(client, "dr_bennett")
    with db.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS n FROM Consultation")
        before = cursor.fetchone()["n"]

    response = client.post("/api/v1/consultations", json=consultation(5000), headers=headers)
    assert response.status_code == 404, response.text

    with db.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS n FROM Consultation")
        assert cursor.fetchone()["n"] == before
