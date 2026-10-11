import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.connection import get_db_connection


def test_patient_registration_login_and_password_change_flow():
    """
    End-to-End Test for:
    1. Registering a new patient auto-creates their User_Account with 'pat_<nic>' and 'Password123!'.
    2. Logging in with the newly generated credentials succeeds and /me resolves Patient_ID.
    3. Changing password enforces validation (wrong current password, short password, same password).
    4. Successful password change invalidates old password and allows login with new password.
    """
    tag = uuid.uuid4().hex[:6]
    # NIC format: 9 digits + 'V'
    nic_digits = "99" + "".join(str((i * 7 + 3) % 10) for i in range(7))
    nic = f"{nic_digits}V"
    clean_username = f"pat_{nic.lower()}"

    client = TestClient(app)

    # 1. Register a new patient through reception/admin (using admin override for registration)
    from app.api.deps import get_current_user
    from app.schemas.user import UserAccount, SystemRoleEnum, AccountStatusEnum

    admin_mock = UserAccount(
        Account_ID=1,
        Username="admin_alana",
        Password_Hash="",
        System_Role=SystemRoleEnum.Admin,
        Account_Status=AccountStatusEnum.Active,
    )
    app.dependency_overrides[get_current_user] = lambda: admin_mock

    payload = {
        "first_name": "Kasun",
        "last_name": f"Bandara{tag}",
        "date_of_birth": "1994-06-15",
        "gender": "Male",
        "nic": nic,
        "contact_number": "+94771239999",
        "email": f"kasun.{tag}@example.com",
        "street_address": "45 Temple Road",
        "city": "Colombo",
        "state_province": "Western Province",
        "postal_code": "00100",
        "emergency_contact": {
            "first_name": "Nimal",
            "last_name": "Bandara",
            "relationship_to_patient": "Brother",
            "contact_number": "+94771238888",
            "street_address": "45 Temple Road",
            "city": "Colombo",
            "postal_code": "00100",
        },
    }

    reg_response = client.post("/api/v1/patients", json=payload)
    assert reg_response.status_code == 201, reg_response.text
    patient_data = reg_response.json()
    patient_id = patient_data["patient_id"]

    # Verify portal_access in response
    assert patient_data["portal_access"]["has_account"] is True
    assert patient_data["portal_access"]["username"] == clean_username

    # Remove dependency override to test real unmocked authentication
    app.dependency_overrides.pop(get_current_user, None)

    try:
        # 2. Login as the newly created patient using default password
        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": clean_username, "password": "Password123!"},
        )
        assert login_response.status_code == 200, login_response.text
        tokens = login_response.json()
        token = tokens["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 3. Call /me to verify role and patient ID
        me_response = client.get("/api/v1/auth/me", headers=headers)
        assert me_response.status_code == 200, me_response.text
        me_data = me_response.json()
        assert me_data["System_Role"] == "Patient"
        assert me_data["Patient_ID"] == patient_id
        assert me_data["First_Name"] == "Kasun"

        # 4. Try changing password with wrong current password -> 400
        fail_curr = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "WrongPassword!", "new_password": "NewSecretPass456!"},
            headers=headers,
        )
        assert fail_curr.status_code == 400
        assert "Current password is incorrect" in fail_curr.json()["detail"]

        # 5. Try changing password with short password (< 6 chars) -> 400
        fail_short = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "Password123!", "new_password": "123"},
            headers=headers,
        )
        assert fail_short.status_code == 400
        assert "at least 6 characters" in fail_short.json()["detail"]

        # 6. Try changing password with same password -> 400
        fail_same = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "Password123!", "new_password": "Password123!"},
            headers=headers,
        )
        assert fail_same.status_code == 400
        assert "cannot be the same" in fail_same.json()["detail"]

        # 7. Successfully change password
        success_change = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "Password123!", "new_password": "NewSecretPass456!"},
            headers=headers,
        )
        assert success_change.status_code == 200
        assert success_change.json()["message"] == "Password changed successfully"

        # 8. Verify old password no longer works
        fail_login = client.post(
            "/api/v1/auth/login",
            data={"username": clean_username, "password": "Password123!"},
        )
        assert fail_login.status_code == 400
        assert "Incorrect username or password" in fail_login.json()["detail"]

        # 9. Verify new password works
        new_login = client.post(
            "/api/v1/auth/login",
            data={"username": clean_username, "password": "NewSecretPass456!"},
        )
        assert new_login.status_code == 200
        new_token = new_login.json()["access_token"]
        assert new_token is not None

    finally:
        # Cleanup created records
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM Audit_Log WHERE Table_Name = 'Patient' AND Record_ID = %s",
                    (str(patient_id),),
                )
                cursor.execute(
                    "DELETE FROM Audit_Log WHERE Table_Name = 'User_Account' AND Record_ID IN (SELECT Account_ID FROM User_Account WHERE Username = %s)",
                    (clean_username,),
                )
                cursor.execute("DELETE FROM Patient WHERE Patient_ID = %s", (patient_id,))
                cursor.execute("DELETE FROM User_Account WHERE Username = %s", (clean_username,))
            conn.commit()
        finally:
            conn.close()
