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
