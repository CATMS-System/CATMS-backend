# terminated staff must not be able to log in or keep using an old token
import random

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.main import app

PASSWORD = "Password123!"


# a throwaway receptionist with a staff row, deleted when the test ends
@pytest.fixture
def staff_user(db):
    username = "recept_term_" + "".join(random.choices("abcdefghij", k=6))
    with db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO User_Account (Username, Password_Hash, System_Role, Account_Status) "
            "VALUES (%s, %s, 'Receptionist', 'Active')",
            (username, get_password_hash(PASSWORD)),
        )
        account_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO Staff (Account_ID, Branch_ID, First_Name, Last_Name, Job_Title, "
            "Contact_Number, Email, Employment_Status) "
            "VALUES (%s, 1, 'Term', 'Test', 'Receptionist', '0770000098', %s, 'Active')",
            (account_id, f"{username}@careflow.com"),
        )
        staff_id = cursor.lastrowid
    db.commit()
    yield username, staff_id
    with db.cursor() as cursor:
        cursor.execute(
            "DELETE FROM Audit_Log WHERE (Table_Name = 'Staff' AND Record_ID = %s) "
            "OR (Table_Name = 'User_Account' AND Record_ID = %s)",
            (str(staff_id), str(account_id)),
        )
        cursor.execute("DELETE FROM Staff WHERE Staff_ID = %s", (staff_id,))
        cursor.execute("DELETE FROM User_Account WHERE Account_ID = %s", (account_id,))
    db.commit()


def login(client, username):
    return client.post("/api/v1/auth/login", data={"username": username, "password": PASSWORD})


def test_terminated_staff_is_blocked(db, staff_user):
    username, staff_id = staff_user
    client = TestClient(app)

    response = login(client, username)
    assert response.status_code == 200, response.text
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200

    with db.cursor() as cursor:
        cursor.execute(
            "UPDATE Staff SET Employment_Status = 'Terminated' WHERE Staff_ID = %s", (staff_id,)
        )
    db.commit()

    # the old token stops working
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 400
    # and a new login is refused
    blocked = login(client, username)
    assert blocked.status_code == 400
    assert blocked.json()["detail"] == "Inactive user"
