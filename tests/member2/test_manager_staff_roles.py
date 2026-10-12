# a branch manager must not be able to create admin or manager accounts
from fastapi.testclient import TestClient

from app.main import app


def manager_headers(client):
    response = client.post(
        "/api/v1/auth/login", data={"username": "mgr_vance", "password": "Password123!"}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def staff_payload(**changes):
    payload = {
        "First_Name": "Role",
        "Last_Name": "Blocked",
        "Job_Title": "Clerk",
        "Contact_Number": "0770000099",
        "Email": "role.blocked@careflow.com",
        "Employment_Status": "Active",
        "Username": "role_blocked_test",
        "Password": "Password123!",
    }
    payload.update(changes)
    return payload


def test_manager_cannot_create_admin_or_manager(db):
    client = TestClient(app)
    headers = manager_headers(client)

    as_admin = client.post("/api/v1/staff", json=staff_payload(System_Role="Admin"), headers=headers)
    assert as_admin.status_code == 403, as_admin.text

    as_manager = client.post(
        "/api/v1/staff", json=staff_payload(System_Role="Branch_Manager"), headers=headers
    )
    assert as_manager.status_code == 403, as_manager.text

    # no role given, but the job title would make it an admin
    by_title = client.post(
        "/api/v1/staff", json=staff_payload(Job_Title="System Admin"), headers=headers
    )
    assert by_title.status_code == 403, by_title.text

    with db.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS n FROM User_Account WHERE Username = 'role_blocked_test'")
        assert cursor.fetchone()["n"] == 0
