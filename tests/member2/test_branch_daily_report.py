# the branch daily report shows scheduled, completed, cancelled and walk-in counts
from fastapi.testclient import TestClient
from app.main import app


def test_branch_daily_report_counts(db):
    client = TestClient(app)
    login = client.post("/api/v1/auth/login", data={"username": "admin_alana", "password": "Password123!"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    with db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO Appointment (Patient_ID, Doctor_ID, Branch_ID, Appointment_Date, Start_Time, "
            "Duration_Minutes, Appointment_Type, Status, Reason_For_Visit) VALUES "
            "(1, 1, 1, '2099-04-06', '09:00:00', 15, 'Standard', 'Scheduled', 'report test'), "
            "(2, 1, 1, '2099-04-06', '09:30:00', 15, 'Walk_In', 'Confirmed', 'report test')"
        )
        db.commit()
    try:
        response = client.get(
            "/api/v1/reports/branch-daily-summary",
            params={"report_date": "2099-04-06", "branch_id": 1},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        row = response.json()[0]
        assert row["Total_Appointments"] == 2
        assert row["Scheduled_Appointments"] == 2
        assert row["Completed_Appointments"] == 0
        assert row["Walk_In_Appointments"] == 1
    finally:
        with db.cursor() as cursor:
            cursor.execute("DELETE FROM Appointment WHERE Reason_For_Visit = 'report test'")
            db.commit()
