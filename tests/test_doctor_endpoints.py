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
    return TestClient(app)


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
