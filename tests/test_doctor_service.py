"""
Automated unit and integration test suite for Doctor and Specialty service layer.
Tests Plain PyMySQL query operations against local Docker MySQL 8.0.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.connection import get_db_connection
from app.services.doctor_service import (
    get_all_specialties,
    get_doctor_specialties,
    get_all_doctors,
    get_doctor_by_id,
    DoctorNotFoundError
)


@pytest.fixture(scope="module")
def db_conn():
    conn = get_db_connection()
    yield conn
    conn.close()


def test_get_all_specialties(db_conn):
    specialties = get_all_specialties(db_conn)
    assert len(specialties) > 0, "Specialties list should not be empty."
    names = [s["Specialty_Name"] for s in specialties]
    assert "Cardiology" in names
    assert "General Medicine" in names


def test_get_all_doctors(db_conn):
    doctors = get_all_doctors(db_conn)
    assert len(doctors) > 0, "Doctors list should not be empty."
    first = doctors[0]
    assert "Doctor_ID" in first
    assert "Full_Name" in first
    assert "License_Number" in first
    assert "Branch_Name" in first
    assert "Specialties" in first


def test_filter_doctors_by_branch(db_conn):
    colombo_doctors = get_all_doctors(db_conn, branch_id=1)
    assert len(colombo_doctors) > 0, "Should return doctors for Colombo Main Clinic."
    for d in colombo_doctors:
        assert d["Branch_ID"] == 1, f"Expected Branch_ID 1, got {d['Branch_ID']}"


def test_filter_doctors_by_specialty(db_conn):
    cardio_doctors = get_all_doctors(db_conn, specialty_id=1)
    assert len(cardio_doctors) > 0, "Should return at least 1 doctor with Cardiology specialty."
    assert any(d["Doctor_ID"] == 1 for d in cardio_doctors)


def test_search_doctors_by_name(db_conn):
    searched = get_all_doctors(db_conn, search="Bennett")
    assert len(searched) == 1, "Should find exactly 1 doctor matching 'Bennett'."
    assert searched[0]["Doctor_ID"] == 1


def test_get_doctor_by_id_success(db_conn):
    doc1 = get_doctor_by_id(db_conn, doctor_id=1)
    assert doc1["Doctor_ID"] == 1
    assert doc1["First_Name"] == "Alexander"
    assert doc1["Last_Name"] == "Bennett"
    assert isinstance(doc1["Specialties"], list)
    assert len(doc1["Specialties"]) > 0


def test_get_doctor_by_id_not_found(db_conn):
    with pytest.raises(DoctorNotFoundError):
        get_doctor_by_id(db_conn, doctor_id=999999)


if __name__ == "__main__":
    conn = get_db_connection()
    try:
        test_get_all_specialties(conn)
        test_get_all_doctors(conn)
        test_filter_doctors_by_branch(conn)
        test_filter_doctors_by_specialty(conn)
        test_search_doctors_by_name(conn)
        test_get_doctor_by_id_success(conn)
        test_get_doctor_by_id_not_found(conn)
        print("All Doctor & Specialty tests passed successfully!")
    finally:
        conn.close()
