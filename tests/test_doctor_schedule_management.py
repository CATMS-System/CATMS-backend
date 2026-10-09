"""
Integration tests for doctor schedule management endpoints:
- POST /api/v1/doctors/{doctor_id}/schedules (Create schedule)
- PUT /api/v1/doctors/schedules/{schedule_id} (Update schedule)
- Validations: start_time < end_time, overlap prevention, branch manager scope restriction
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_user
from app.db.connection import get_db_connection
from app.schemas.user import UserAccount, SystemRoleEnum, AccountStatusEnum


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_admin():
    mock_admin = UserAccount(
        Account_ID=1,
        Username="admin_test",
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


@pytest.fixture
def branch_manager_setup():
    """
    Creates a temporary branch manager associated with Branch 1.
    """
    conn = get_db_connection()
    manager_account_id = None
    manager_staff_id = None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO User_Account (Username, Password_Hash, System_Role, Account_Status)
                VALUES ('bm_test_schedule', 'hash123', 'Branch_Manager', 'Active')
                """
            )
            manager_account_id = cur.lastrowid
            cur.execute(
                """
                INSERT INTO Staff (Account_ID, Branch_ID, First_Name, Last_Name, Job_Title, Contact_Number, Email, Employment_Status)
                VALUES (%s, 1, 'Manager', 'BranchOne', 'Clinic Manager', '+94 77 999 1111', 'bm1@test.lk', 'Active')
                """,
                (manager_account_id,)
            )
            manager_staff_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()

    mock_mgr = UserAccount(
        Account_ID=manager_account_id,
        Username="bm_test_schedule",
        Password_Hash="",
        System_Role=SystemRoleEnum.Branch_Manager,
        Account_Status=AccountStatusEnum.Active,
    )

    yield mock_mgr

    # Cleanup
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if manager_staff_id:
                cur.execute("DELETE FROM Staff WHERE Staff_ID = %s", (manager_staff_id,))
            if manager_account_id:
                cur.execute("DELETE FROM User_Account WHERE Account_ID = %s", (manager_account_id,))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def cleanup_schedules():
    created_ids = []
    yield created_ids
    if created_ids:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                format_strings = ",".join(["%s"] * len(created_ids))
                cur.execute(f"DELETE FROM Doctor_Schedule WHERE Schedule_ID IN ({format_strings})", tuple(created_ids))
            conn.commit()
        finally:
            conn.close()


def test_create_doctor_schedule_success(client, auth_admin, cleanup_schedules):
    payload = {
        "Branch_ID": 1,
        "Day_Of_Week": "Sunday",
        "Start_Time": "14:00:00",
        "End_Time": "18:00:00",
        "Availability_Status": "Active",
    }
    resp = client.post("/api/v1/doctors/1/schedules", json=payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["Doctor_ID"] == 1
    assert data["Branch_ID"] == 1
    assert data["Day_Of_Week"] == "Sunday"
    assert data["Start_Time_Str"] == "14:00:00"
    assert data["End_Time_Str"] == "18:00:00"
    assert data["Shift_Duration_Minutes"] == 240
    assert data["Availability_Status"] == "Active"

    cleanup_schedules.append(data["Schedule_ID"])


def test_create_doctor_schedule_overlap_conflict(client, auth_admin, cleanup_schedules):
    payload1 = {
        "Branch_ID": 1,
        "Day_Of_Week": "Sunday",
        "Start_Time": "14:00:00",
        "End_Time": "18:00:00",
        "Availability_Status": "Active",
    }
    resp1 = client.post("/api/v1/doctors/1/schedules", json=payload1)
    assert resp1.status_code == 201
    cleanup_schedules.append(resp1.json()["Schedule_ID"])

    # Attempt overlapping schedule: 15:00 - 17:00
    payload2 = {
        "Branch_ID": 1,
        "Day_Of_Week": "Sunday",
        "Start_Time": "15:00:00",
        "End_Time": "17:00:00",
        "Availability_Status": "Active",
    }
    resp2 = client.post("/api/v1/doctors/1/schedules", json=payload2)
    assert resp2.status_code == 409
    assert "overlapping" in resp2.json()["detail"].lower()


def test_create_doctor_schedule_invalid_time_range(client, auth_admin):
    # Start time after end time
    payload = {
        "Branch_ID": 1,
        "Day_Of_Week": "Sunday",
        "Start_Time": "18:00:00",
        "End_Time": "14:00:00",
        "Availability_Status": "Active",
    }
    resp = client.post("/api/v1/doctors/1/schedules", json=payload)
    assert resp.status_code == 422
    assert "start time must be strictly before end time" in resp.json()["detail"].lower()


def test_create_doctor_schedule_nonexistent_doctor(client, auth_admin):
    payload = {
        "Branch_ID": 1,
        "Day_Of_Week": "Sunday",
        "Start_Time": "09:00:00",
        "End_Time": "12:00:00",
        "Availability_Status": "Active",
    }
    resp = client.post("/api/v1/doctors/99999/schedules", json=payload)
    assert resp.status_code == 404


def test_branch_manager_scope_restriction(client, branch_manager_setup, cleanup_schedules):
    previous = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: branch_manager_setup

    try:
        # Branch manager for Branch 1 attempting to schedule for Branch 2 should fail with 403
        payload_other_branch = {
            "Branch_ID": 2,
            "Day_Of_Week": "Sunday",
            "Start_Time": "08:00:00",
            "End_Time": "12:00:00",
            "Availability_Status": "Active",
        }
        resp_forbidden = client.post("/api/v1/doctors/1/schedules", json=payload_other_branch)
        assert resp_forbidden.status_code == 403
        assert "own branch" in resp_forbidden.json()["detail"].lower()

        # Branch manager for Branch 1 scheduling for Branch 1 should succeed with 201
        payload_own_branch = {
            "Branch_ID": 1,
            "Day_Of_Week": "Sunday",
            "Start_Time": "08:00:00",
            "End_Time": "11:00:00",
            "Availability_Status": "Active",
        }
        resp_allowed = client.post("/api/v1/doctors/1/schedules", json=payload_own_branch)
        assert resp_allowed.status_code == 201
        cleanup_schedules.append(resp_allowed.json()["Schedule_ID"])
    finally:
        if previous is not None:
            app.dependency_overrides[get_current_user] = previous
        else:
            app.dependency_overrides.pop(get_current_user, None)


def test_update_doctor_schedule_success(client, auth_admin, cleanup_schedules):
    # First create a schedule
    create_payload = {
        "Branch_ID": 1,
        "Day_Of_Week": "Sunday",
        "Start_Time": "13:00:00",
        "End_Time": "16:00:00",
        "Availability_Status": "Active",
    }
    create_resp = client.post("/api/v1/doctors/1/schedules", json=create_payload)
    assert create_resp.status_code == 201
    schedule_id = create_resp.json()["Schedule_ID"]
    cleanup_schedules.append(schedule_id)

    # Now update it
    update_payload = {
        "Start_Time": "13:30:00",
        "End_Time": "17:30:00",
        "Availability_Status": "Suspended",
    }
    update_resp = client.put(f"/api/v1/doctors/schedules/{schedule_id}", json=update_payload)
    assert update_resp.status_code == 200
    data = update_resp.json()
    assert data["Start_Time_Str"] == "13:30:00"
    assert data["End_Time_Str"] == "17:30:00"
    assert data["Availability_Status"] == "Suspended"
    assert data["Shift_Duration_Minutes"] == 240
