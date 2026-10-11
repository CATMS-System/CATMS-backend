# bad input gets a clear 4xx answer, never a 500 with internal error text
from fastapi.testclient import TestClient
from app.main import app


def headers_for(client, username):
    response = client.post(
        "/api/v1/auth/login", data={"username": username, "password": "Password123!"}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_bad_input_returns_4xx(db):
    client = TestClient(app)
    admin = headers_for(client, "admin_alana")
    branches = client.get("/api/v1/branches", headers=admin).json()
    first = branches[0]
    duplicate = client.post(
        "/api/v1/branches",
        json={
            "Branch_Name": first["Branch_Name"],
            "Street_Address": "1 Test Road",
            "City": "Colombo",
            "State_Province": "Western",
            "Postal_Code": "00100",
            "Contact_Number": "+94110000000",
            "Email": "duplicate.branch@example.com",
        },
        headers=admin,
    )
    assert duplicate.status_code == 409, duplicate.text
    bad_time = client.post(
        "/api/v1/appointments",
        json={
            "patient_id": 1,
            "doctor_id": 1,
            "branch_id": 1,
            "appointment_date": "2099-01-05",
            "start_time": "abc",
            "reason_for_visit": "Checkup",
        },
        headers=admin,
    )
    assert bad_time.status_code == 422, bad_time.text
    missing_schedule = client.put(
        "/api/v1/doctors/1/schedules/999999",
        json={"availability_status": "Active"},
        headers=admin,
    )
    assert missing_schedule.status_code == 404, missing_schedule.text
