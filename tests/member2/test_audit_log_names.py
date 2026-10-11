# the audit log shows who did each change and at which branch
from fastapi.testclient import TestClient
from app.main import app


def test_audit_log_has_names(db):
    client = TestClient(app)
    login = client.post(
        "/api/v1/auth/login", data={"username": "admin_alana", "password": "Password123!"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.get("/api/v1/audit-logs", headers=headers)
    assert response.status_code == 200, response.text
    logs = response.json()
    assert logs
    assert all(log["Performed_By"] for log in logs)
    assert any(log["Affected_Branch"] for log in logs)
