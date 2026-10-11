# password change, checked with a staff account against the real local mysql
import random

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.main import app

OLD_PASSWORD = "Password123!"
NEW_PASSWORD = "NewSecretPass456!"


# a throwaway receptionist account, deleted when the test ends
@pytest.fixture
def staff_login(db):
    username = "recept_pw_" + "".join(random.choices("abcdefghij", k=6))
    with db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO User_Account (Username, Password_Hash, System_Role, Account_Status) "
            "VALUES (%s, %s, 'Receptionist', 'Active')",
            (username, get_password_hash(OLD_PASSWORD)),
        )
    db.commit()
    yield username
    with db.cursor() as cursor:
        cursor.execute(
            "DELETE FROM Audit_Log WHERE Table_Name = 'User_Account' AND Record_ID IN "
            "(SELECT Account_ID FROM User_Account WHERE Username = %s)",
            (username,),
        )
        cursor.execute("DELETE FROM User_Account WHERE Username = %s", (username,))
    db.commit()


def login(client, username, password):
    return client.post("/api/v1/auth/login", data={"username": username, "password": password})


def change(client, headers, current, new):
    return client.post(
        "/api/v1/auth/change-password",
        json={"current_password": current, "new_password": new},
        headers=headers,
    )


def test_change_password(staff_login):
    client = TestClient(app)
    response = login(client, staff_login, OLD_PASSWORD)
    assert response.status_code == 200, response.text
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    wrong_current = change(client, headers, "WrongPassword!", NEW_PASSWORD)
    assert wrong_current.status_code == 400
    assert "Current password is incorrect" in wrong_current.json()["detail"]

    too_short = change(client, headers, OLD_PASSWORD, "123")
    assert too_short.status_code == 400
    assert "at least 6 characters" in too_short.json()["detail"]

    same = change(client, headers, OLD_PASSWORD, OLD_PASSWORD)
    assert same.status_code == 400
    assert "cannot be the same" in same.json()["detail"]

    ok = change(client, headers, OLD_PASSWORD, NEW_PASSWORD)
    assert ok.status_code == 200
    assert ok.json()["message"] == "Password changed successfully"

    # only the new password works now
    old_login = login(client, staff_login, OLD_PASSWORD)
    assert old_login.status_code == 400
    assert "Incorrect username or password" in old_login.json()["detail"]
    assert login(client, staff_login, NEW_PASSWORD).status_code == 200
