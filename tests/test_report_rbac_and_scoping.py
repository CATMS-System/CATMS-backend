from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.main import app
from app.schemas.user import AccountStatusEnum, SystemRoleEnum, UserAccount


@pytest.fixture(autouse=True)
def clean_dependencies():
    yield
    app.dependency_overrides.clear()


def make_user(account_id: int, role: SystemRoleEnum, username: str = "test_user") -> UserAccount:
    return UserAccount(
        Account_ID=account_id,
        Username=username,
        Password_Hash="",
        System_Role=role,
        Account_Status=AccountStatusEnum.Active,
    )


def test_billing_staff_scopes_to_own_branch_and_cannot_query_other_branch():
    """Billing_Staff role can access reports for their assigned branch, but receives 403 for other branches."""
    client = TestClient(app)

    fake_db = MagicMock()
    fake_cursor = MagicMock()
    # Mock get_staff_branch_id: Staff query returns Branch_ID 2
    fake_cursor.fetchone.return_value = {"Branch_ID": 2}
    fake_cursor.fetchall.return_value = []
    fake_db.cursor.return_value.__enter__.return_value = fake_cursor

    app.dependency_overrides[get_db] = lambda: fake_db
    app.dependency_overrides[get_current_user] = lambda: make_user(
        account_id=201, role=SystemRoleEnum.Billing_Staff, username="billing_officer"
    )

    # 1. Branch daily summary for own branch 2
    res = client.get("/api/v1/reports/branch-daily-summary?report_date=2026-08-15&branch_id=2")
    assert res.status_code == 200

    # 2. Outstanding balances without branch filter (automatically scoped to branch 2)
    res2 = client.get("/api/v1/reports/outstanding-balances")
    assert res2.status_code == 200

    # 3. Requesting other branch 1 receives 403
    res3 = client.get("/api/v1/reports/branch-daily-summary?report_date=2026-08-15&branch_id=1")
    assert res3.status_code == 403
    assert "Billing staff can only view reports for their own branch" in res3.json()["detail"]


def test_branch_manager_can_access_own_branch():
    """Branch_Manager can access reports for their assigned branch."""
    client = TestClient(app)

    fake_db = MagicMock()
    fake_cursor = MagicMock()
    # Mock get_staff_branch_id: Staff query for Branch_ID returns 1
    fake_cursor.fetchone.return_value = {"Branch_ID": 1}
    fake_cursor.fetchall.return_value = []
    fake_db.cursor.return_value.__enter__.return_value = fake_cursor

    app.dependency_overrides[get_db] = lambda: fake_db
    app.dependency_overrides[get_current_user] = lambda: make_user(
        account_id=101, role=SystemRoleEnum.Branch_Manager, username="colombo_manager"
    )

    # Querying own branch explicitly
    res = client.get("/api/v1/reports/branch-daily-summary?report_date=2026-08-15&branch_id=1")
    assert res.status_code == 200


def test_branch_manager_omitting_branch_defaults_to_own_branch():
    """Branch_Manager omitting branch_id defaults to their assigned branch without 403."""
    client = TestClient(app)

    fake_db = MagicMock()
    fake_cursor = MagicMock()
    fake_cursor.fetchone.return_value = {"Branch_ID": 1}
    fake_cursor.fetchall.return_value = []
    fake_db.cursor.return_value.__enter__.return_value = fake_cursor

    app.dependency_overrides[get_db] = lambda: fake_db
    app.dependency_overrides[get_current_user] = lambda: make_user(
        account_id=101, role=SystemRoleEnum.Branch_Manager, username="colombo_manager"
    )

    res = client.get("/api/v1/reports/outstanding-balances")
    assert res.status_code == 200


def test_branch_manager_cannot_access_other_branch_reports():
    """Branch_Manager requesting a different branch receives 403 Forbidden."""
    client = TestClient(app)

    fake_db = MagicMock()
    fake_cursor = MagicMock()
    # Assigned branch is 1
    fake_cursor.fetchone.return_value = {"Branch_ID": 1}
    fake_db.cursor.return_value.__enter__.return_value = fake_cursor

    app.dependency_overrides[get_db] = lambda: fake_db
    app.dependency_overrides[get_current_user] = lambda: make_user(
        account_id=101, role=SystemRoleEnum.Branch_Manager, username="colombo_manager"
    )

    # Attempting to query branch 2
    res = client.get("/api/v1/reports/branch-daily-summary?report_date=2026-08-15&branch_id=2")
    assert res.status_code == 403
    assert "Branch managers can only view reports for their own branch." in res.json()["detail"]

    # Attempting to query branch 2 for doctor-revenue
    res2 = client.get("/api/v1/reports/doctor-revenue?start_date=2026-08-01&end_date=2026-08-31&branch_id=2")
    assert res2.status_code == 403
    assert "Branch managers can only view reports for their own branch." in res2.json()["detail"]


def test_branch_manager_without_assigned_branch_is_rejected():
    """Branch_Manager with no Staff record or NULL Branch_ID receives 403 Forbidden."""
    client = TestClient(app)

    fake_db = MagicMock()
    fake_cursor = MagicMock()
    fake_cursor.fetchone.return_value = None  # No staff record found
    fake_db.cursor.return_value.__enter__.return_value = fake_cursor

    app.dependency_overrides[get_db] = lambda: fake_db
    app.dependency_overrides[get_current_user] = lambda: make_user(
        account_id=999, role=SystemRoleEnum.Branch_Manager, username="unassigned_manager"
    )

    res = client.get("/api/v1/reports/branch-daily-summary?report_date=2026-08-15&branch_id=1")
    assert res.status_code == 403
    assert "Branch manager has no assigned branch." in res.json()["detail"]


def test_unauthorized_roles_cannot_access_reports():
    """Receptionist, Patient, Doctor cannot access reports."""
    client = TestClient(app)

    for role in [SystemRoleEnum.Receptionist, SystemRoleEnum.Patient, SystemRoleEnum.Doctor]:
        app.dependency_overrides[get_current_user] = lambda r=role: make_user(
            account_id=300, role=r, username="unauth_user"
        )
        res = client.get("/api/v1/reports/branch-daily-summary?report_date=2026-08-15")
        assert res.status_code == 403
        assert "Operation not permitted" in res.json()["detail"]
