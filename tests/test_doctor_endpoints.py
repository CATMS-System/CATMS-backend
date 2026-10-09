"""
Unit and integration tests for Doctor and Specialty API endpoints.
Tests route handling, query filtering, path parameter validation, 
and HTTP error responses via FastAPI TestClient.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="module")
def client():
    from app.api.deps import get_current_user
    from app.schemas.user import UserAccount, SystemRoleEnum, AccountStatusEnum
    mock_user = UserAccount(
        Account_ID=1,
        Username="doctor_test_user",
        Password_Hash="",
        System_Role=SystemRoleEnum.Receptionist,
        Account_Status=AccountStatusEnum.Active,
    )
    previous = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        if previous is not None:
            app.dependency_overrides[get_current_user] = previous
        else:
            app.dependency_overrides.pop(get_current_user, None)


def test_list_all_doctors(client):
    """Verifies GET /api/v1/doctors returns all seeded doctors."""
    response = client.get("/api/v1/doctors")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 3

    first_doctor = data[0]
    assert "Doctor_ID" in first_doctor
    assert "Full_Name" in first_doctor
    assert "Branch_Name" in first_doctor
    assert "Specialties" in first_doctor
    assert "Standard_Consultation_Fee" in first_doctor


def test_filter_doctors_by_branch(client):
    """Verifies branch filtering returns only physicians for that branch."""
    response = client.get("/api/v1/doctors?branch_id=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert all(doc["Branch_ID"] == 1 for doc in data)


def test_filter_doctors_by_specialty(client):
    """Verifies specialty filtering returns only doctors with that specialty."""
    response = client.get("/api/v1/doctors?specialty_id=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    for doc in data:
        assert "Cardiology" in doc["Specialties"]


def test_search_doctors_by_name(client):
    """Verifies text search queries matching doctor names."""
    response = client.get("/api/v1/doctors?search=Bennett")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["Last_Name"] == "Bennett"


def test_get_doctor_by_id_success(client):
    """Verifies GET /api/v1/doctors/{id} returns detailed physician profile."""
    response = client.get("/api/v1/doctors/1")
    assert response.status_code == 200
    data = response.json()
    assert data["Doctor_ID"] == 1
    assert data["First_Name"] == "Alexander"
    assert data["Last_Name"] == "Bennett"
    assert isinstance(data["Specialties"], list)
    assert len(data["Specialties"]) >= 1
    assert "Specialty_Name" in data["Specialties"][0]


def test_get_doctor_by_id_not_found(client):
    """Verifies GET /api/v1/doctors/{id} returns 404 for unknown doctor."""
    response = client.get("/api/v1/doctors/999999")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "999999" in data["detail"]


def test_list_all_specialties(client):
    """Verifies GET /api/v1/specialties returns catalog of specialties with doctor counts."""
    response = client.get("/api/v1/specialties")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 5

    cardiology = next((s for s in data if s["Specialty_Name"] == "Cardiology"), None)
    assert cardiology is not None
    assert cardiology["Doctor_Count"] >= 1


def test_list_specialties_alias(client):
    """Verifies GET /api/v1/doctors/specialties convenience alias returns identical catalog."""
    response = client.get("/api/v1/doctors/specialties")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 5


def test_get_doctor_schedules_success(client):
    """Verifies GET /api/v1/doctors/{id}/schedules returns weekly shift blocks."""
    response = client.get("/api/v1/doctors/1/schedules")
    assert response.status_code == 200
    schedules = response.json()
    assert isinstance(schedules, list)
    assert len(schedules) >= 3

    first = schedules[0]
    assert "Schedule_ID" in first
    assert "Doctor_ID" in first
    assert first["Doctor_ID"] == 1
    assert "Branch_Name" in first
    assert "Day_Of_Week" in first
    assert "Shift_Duration_Minutes" in first


def test_get_doctor_schedules_filter_branch(client):
    """Verifies branch_id query param filters doctor schedules."""
    response = client.get("/api/v1/doctors/1/schedules?branch_id=1")
    assert response.status_code == 200
    schedules = response.json()
    assert all(s["Branch_ID"] == 1 for s in schedules)


def test_get_doctor_schedules_not_found(client):
    """Verifies 404 response for non-existent doctor schedule query."""
    response = client.get("/api/v1/doctors/999999/schedules")
    assert response.status_code == 404
    assert "detail" in response.json()


def test_get_doctor_available_slots_success(client):
    """
    Verifies GET /api/v1/doctors/{id}/available-slots computes available booking intervals
    and correctly excludes occupied appointment slots (e.g. 09:00:00 on 2026-08-23).
    """
    response = client.get("/api/v1/doctors/1/available-slots?date=2026-08-23&duration_minutes=30")
    assert response.status_code == 200
    slots = response.json()
    assert isinstance(slots, list)
    assert len(slots) > 0

    # Ensure all slots have correct structure
    for slot in slots:
        assert "Start_Time" in slot
        assert "End_Time" in slot
        assert "Duration_Minutes" in slot
        assert slot["Duration_Minutes"] == 30
        assert "Branch_Name" in slot

    # Confirm occupied slot 09:00:00 is EXCLUDED
    occupied_found = any(s["Start_Time"] == "09:00:00" for s in slots)
    assert not occupied_found, "Slot 09:00:00 is occupied by Appointment #1 and must be excluded!"

    # Confirm adjacent slot 09:30:00 is available
    assert any(s["Start_Time"] == "09:30:00" for s in slots)


def test_get_doctor_available_slots_not_found(client):
    """Verifies 404 response when querying available slots for non-existent doctor."""
    response = client.get("/api/v1/doctors/999999/available-slots?date=2026-08-23")
    assert response.status_code == 404
    assert "detail" in response.json()
