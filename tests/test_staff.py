import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_user
from app.schemas.user import UserAccount, SystemRoleEnum, AccountStatusEnum


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_branch_manager_1():
    # Account_ID 6 is Marcus Vance, Branch Manager for Branch 1 in seed data
    mock_mgr = UserAccount(
        Account_ID=6,
        Username="mgr_vance",
        Password_Hash="",
        System_Role=SystemRoleEnum.Branch_Manager,
        Account_Status=AccountStatusEnum.Active,
    )
    previous = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: mock_mgr
    yield mock_mgr
    if previous is not None:
        app.dependency_overrides[get_current_user] = previous
    else:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def auth_doctor():
    mock_doc = UserAccount(
        Account_ID=2,
        Username="dr_bennett",
        Password_Hash="",
        System_Role=SystemRoleEnum.Doctor,
        Account_Status=AccountStatusEnum.Active,
    )
    previous = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: mock_doc
    yield mock_doc
    if previous is not None:
        app.dependency_overrides[get_current_user] = previous
    else:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def auth_patient():
    mock_pat = UserAccount(
        Account_ID=11,
        Username="pat_johndoe",
        Password_Hash="",
        System_Role=SystemRoleEnum.Patient,
        Account_Status=AccountStatusEnum.Active,
    )
    previous = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: mock_pat
    yield mock_pat
    if previous is not None:
        app.dependency_overrides[get_current_user] = previous
    else:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def auth_admin():
    mock_admin = UserAccount(
        Account_ID=1,
        Username="admin_alana",
        Password_Hash="",
        System_Role=SystemRoleEnum.Admin,
        Account_Status=AccountStatusEnum.Active,
    )
    previous = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: mock_admin
    yield mock_admin
    if previous is not None:
        app.dependency_overrides[get_current_user] = previous
    else:
        app.dependency_overrides.pop(get_current_user, None)


def test_branch_manager_update_staff_own_branch_succeeds(client, auth_branch_manager_1):
    # Staff 1 belongs to Branch 1
    response = client.put(
        "/api/v1/staff/1",
        json={"Job_Title": "Consultant Cardiologist"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["Staff_ID"] == 1
    assert data["Branch_ID"] == 1


def test_branch_manager_update_staff_other_branch_fails(client, auth_branch_manager_1):
    # Staff 2 belongs to Branch 2
    response = client.put(
        "/api/v1/staff/2",
        json={"Job_Title": "Senior GP"}
    )
    assert response.status_code == 403
    assert "Branch managers can only modify staff within their own branch" in response.json()["detail"]


def test_doctor_get_staff_does_not_receive_contact_or_email(client, auth_doctor):
    response = client.get("/api/v1/staff")
    assert response.status_code == 200
    staff_list = response.json()
    assert len(staff_list) > 0
    for staff in staff_list:
        assert "Contact_Number" not in staff
        assert "Email" not in staff
        assert "First_Name" in staff
        assert "Job_Title" in staff

    detail_resp = client.get("/api/v1/staff/1")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert "Contact_Number" not in detail
    assert "Email" not in detail
    assert detail["Staff_ID"] == 1


def test_patient_get_staff_does_not_receive_contact_or_email(client, auth_patient):
    response = client.get("/api/v1/staff")
    assert response.status_code == 200
    staff_list = response.json()
    assert len(staff_list) > 0
    for staff in staff_list:
        assert "Contact_Number" not in staff
        assert "Email" not in staff

    detail_resp = client.get("/api/v1/staff/1")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert "Contact_Number" not in detail
    assert "Email" not in detail


def test_admin_get_staff_receives_full_contact_and_email(client, auth_admin):
    response = client.get("/api/v1/staff")
    assert response.status_code == 200
    staff_list = response.json()
    assert len(staff_list) > 0
    first = staff_list[0]
    assert "Contact_Number" in first
    assert "Email" in first

    detail_resp = client.get("/api/v1/staff/1")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert "Contact_Number" in detail
    assert "Email" in detail


@pytest.fixture
def cleanup_staff():
    from app.db.connection import get_db_connection
    created_staff_ids = []
    yield created_staff_ids
    if created_staff_ids:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                for sid in created_staff_ids:
                    cur.execute("SELECT Account_ID FROM Staff WHERE Staff_ID = %s", (sid,))
                    row = cur.fetchone()
                    acc_id = row["Account_ID"] if row else None
                    cur.execute("DELETE FROM Staff WHERE Staff_ID = %s", (sid,))
                    if acc_id:
                        cur.execute("DELETE FROM User_Account WHERE Account_ID = %s", (acc_id,))
            conn.commit()
        finally:
            conn.close()


def test_branch_manager_create_staff_own_branch_succeeds(client, auth_branch_manager_1, cleanup_staff):
    payload = {
        "First_Name": "Praveen",
        "Last_Name": "Silva",
        "Job_Title": "Front Desk Receptionist",
        "Contact_Number": "0771234567",
        "Email": "praveen.recept@example.com",
        "Branch_ID": 1,
        "System_Role": "Receptionist"
    }
    response = client.post("/api/v1/staff", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["Branch_ID"] == 1
    assert data["First_Name"] == "Praveen"
    cleanup_staff.append(data["Staff_ID"])


def test_branch_manager_create_staff_different_branch_rejected(client, auth_branch_manager_1):
    payload = {
        "First_Name": "Malik",
        "Last_Name": "Peiris",
        "Job_Title": "Front Desk Receptionist",
        "Contact_Number": "0771234568",
        "Email": "malik.recept@example.com",
        "Branch_ID": 2,
        "System_Role": "Receptionist"
    }
    response = client.post("/api/v1/staff", json=payload)
    assert response.status_code == 403
    assert response.json()["detail"] == "Branch managers can only add staff to their own branch"


def test_branch_manager_create_doctor_own_branch_succeeds(client, auth_branch_manager_1, cleanup_staff):
    payload = {
        "First_Name": "Kamani",
        "Last_Name": "Ratnayake",
        "Job_Title": "Consultant Dermatologist",
        "Contact_Number": "0775551234",
        "Email": "kamani.derma@example.com",
        "Branch_ID": 1,
        "System_Role": "Doctor",
        "License_Number": "SLMC-DERMA-9911",
        "Standard_Consultation_Fee": "3000.00"
    }
    response = client.post("/api/v1/staff", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["Branch_ID"] == 1
    assert data["License_Number"] == "SLMC-DERMA-9911"
    cleanup_staff.append(data["Staff_ID"])

    # Confirm Doctor table record
    from app.db.connection import get_db_connection
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM Doctor WHERE Doctor_ID = %s", (data["Staff_ID"],))
            doc_row = cur.fetchone()
            assert doc_row is not None
            assert doc_row["License_Number"] == "SLMC-DERMA-9911"
    finally:
        conn.close()


def test_admin_create_staff_any_branch_succeeds(client, auth_admin, cleanup_staff):
    payload = {
        "First_Name": "Anura",
        "Last_Name": "Dissanayake",
        "Job_Title": "Accounts Assistant",
        "Contact_Number": "0773334455",
        "Email": "anura.accounts@example.com",
        "Branch_ID": 2,
        "System_Role": "Billing_Staff"
    }
    response = client.post("/api/v1/staff", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["Branch_ID"] == 2
    assert data["First_Name"] == "Anura"
    cleanup_staff.append(data["Staff_ID"])

