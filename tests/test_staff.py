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
