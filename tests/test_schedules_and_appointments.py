"""
Automated unit and integration test suite for Doctor Schedules and Appointment Query layer.
Tests Plain PyMySQL query operations against local Docker MySQL 8.0.
"""

import os
import sys
import pytest
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.connection import get_db_connection
from app.services.doctor_service import get_doctor_schedules
from app.services.appointment_service import (
    get_appointment_by_id,
    get_appointments_by_date,
    get_appointment_status_counts
)


@pytest.fixture(scope="module")
def db_conn():
    conn = get_db_connection()
    yield conn
    conn.close()


def test_get_doctor_schedules(db_conn):
    schedules = get_doctor_schedules(db_conn, doctor_id=1)
    assert len(schedules) >= 3, "Doctor 1 should have at least 3 active schedule shifts."
    days = [s["Day_Of_Week"] for s in schedules]
    assert "Monday" in days
    assert "Wednesday" in days
    assert "Friday" in days
    first = schedules[0]
    assert "Branch_Name" in first
    assert "Shift_Duration_Minutes" in first
    assert first["Shift_Duration_Minutes"] > 0
    assert "Start_Time_Str" in first
    assert "End_Time_Str" in first


def test_get_doctor_schedules_empty(db_conn):
    schedules = get_doctor_schedules(db_conn, doctor_id=999999)
    assert len(schedules) == 0, "Non-existent doctor should return empty schedule list."


def test_get_appointment_by_id_found(db_conn):
    appt = get_appointment_by_id(db_conn, appointment_id=1)
    assert appt is not None, "Seeded appointment #1 must exist."
    assert appt["Appointment_ID"] == 1
    assert appt["Patient_Name"] == "John Doe"
    assert appt["Doctor_Name"] == "Alexander Bennett"
    assert appt["Branch_Name"] == "Colombo Main Clinic"
    assert appt["Status"] == "Completed"


def test_get_appointment_by_id_not_found(db_conn):
    appt = get_appointment_by_id(db_conn, appointment_id=999999)
    assert appt is None, "Non-existent appointment should return None."


def test_get_appointments_by_date(db_conn):
    appts = get_appointments_by_date(db_conn, appointment_date=date(2026, 8, 23))
    assert len(appts) >= 3, "Should find seeded appointments on 2026-08-23."
    for a in appts:
        assert a["Appointment_Date"] == date(2026, 8, 23)
        assert "Patient_Name" in a
        assert "Doctor_Name" in a


def test_get_appointments_filter_doctor(db_conn):
    appts = get_appointments_by_date(db_conn, doctor_id=1)
    assert len(appts) >= 3, "Doctor 1 should have multiple scheduled/completed appointments."
    for a in appts:
        assert a["Doctor_ID"] == 1


def test_get_appointment_status_counts(db_conn):
    counts = get_appointment_status_counts(db_conn)
    assert counts["Total"] >= 7, "Total seeded appointments should be at least 7."
    assert counts["Completed"] > 0
    assert counts["Walk_In"] >= 1
    assert "Scheduled" in counts
    assert "Confirmed" in counts
    assert "Cancelled" in counts


if __name__ == "__main__":
    conn = get_db_connection()
    try:
        test_get_doctor_schedules(conn)
        test_get_doctor_schedules_empty(conn)
        test_get_appointment_by_id_found(conn)
        test_get_appointment_by_id_not_found(conn)
        test_get_appointments_by_date(conn)
        test_get_appointments_filter_doctor(conn)
        test_get_appointment_status_counts(conn)
        print("All Day 5 Doctor Schedules & Appointment queries passed successfully!")
    finally:
        conn.close()
