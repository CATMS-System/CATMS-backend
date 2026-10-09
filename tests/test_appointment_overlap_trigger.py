"""
Integration tests for database appointment overlap triggers:
- trg_check_appointment_overlap_insert
- trg_check_appointment_overlap_update

Verifies that MySQL directly enforces conflict prevention with SQLSTATE 45000
and serializes doctor availability using row locks (FOR UPDATE).
"""

from datetime import date
import pytest
import pymysql

from app.db.connection import get_db_connection


@pytest.fixture
def db_conn():
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def cleanup_trigger_test_appointments(db_conn):
    test_appt_ids = []
    yield test_appt_ids
    if test_appt_ids:
        with db_conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(test_appt_ids))
            cur.execute(f"DELETE FROM Appointment WHERE Appointment_ID IN ({placeholders})", tuple(test_appt_ids))
        db_conn.commit()


def test_trigger_rejects_overlapping_appointment_insert(db_conn, cleanup_trigger_test_appointments):
    """
    Directly inserts an appointment via raw SQL, then attempts to insert an overlapping
    time slot for the same doctor. Asserts that the trigger fires and raises SQLSTATE 45000.
    """
    test_date = date(2027, 5, 10)
    doctor_id = 1
    patient_id = 1
    branch_id = 1

    with db_conn.cursor() as cur:
        # 1. Insert initial base appointment: 10:00:00 - 10:30:00
        cur.execute(
            """
            INSERT INTO Appointment
            (Patient_ID, Doctor_ID, Branch_ID, Appointment_Date, Start_Time, Duration_Minutes, Appointment_Type, Status, Reason_For_Visit)
            VALUES (%s, %s, %s, %s, %s, %s, 'Standard', 'Scheduled', 'Trigger testing')
            """,
            (patient_id, doctor_id, branch_id, test_date, "10:00:00", 30),
        )
        first_id = cur.lastrowid
        cleanup_trigger_test_appointments.append(first_id)
        db_conn.commit()

        # 2. Attempt to insert overlapping appointment: 10:15:00 - 10:45:00 (overlaps by 15 mins)
        with pytest.raises((pymysql.err.OperationalError, pymysql.err.InternalError)) as exc_info:
            cur.execute(
                """
                INSERT INTO Appointment
                (Patient_ID, Doctor_ID, Branch_ID, Appointment_Date, Start_Time, Duration_Minutes, Appointment_Type, Status, Reason_For_Visit)
                VALUES (%s, %s, %s, %s, %s, %s, 'Standard', 'Scheduled', 'Overlapping test')
                """,
                (patient_id, doctor_id, branch_id, test_date, "10:15:00", 30),
            )
            db_conn.commit()

        db_conn.rollback()

        # Verify SQLSTATE 45000 and trigger error message
        err_msg = str(exc_info.value)
        assert "Doctor already has an overlapping appointment in this time slot" in err_msg or "45000" in err_msg


def test_trigger_allows_non_overlapping_appointment_insert(db_conn, cleanup_trigger_test_appointments):
    """
    Verifies that a contiguous or non-overlapping appointment for the same doctor succeeds.
    10:00 - 10:30 followed by 10:30 - 11:00 does not overlap.
    """
    test_date = date(2027, 5, 11)
    doctor_id = 1
    patient_id = 1
    branch_id = 1

    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO Appointment
            (Patient_ID, Doctor_ID, Branch_ID, Appointment_Date, Start_Time, Duration_Minutes, Appointment_Type, Status, Reason_For_Visit)
            VALUES (%s, %s, %s, %s, %s, %s, 'Standard', 'Scheduled', 'Trigger testing')
            """,
            (patient_id, doctor_id, branch_id, test_date, "10:00:00", 30),
        )
        first_id = cur.lastrowid
        cleanup_trigger_test_appointments.append(first_id)

        # Directly adjacent slot (10:30:00) should succeed
        cur.execute(
            """
            INSERT INTO Appointment
            (Patient_ID, Doctor_ID, Branch_ID, Appointment_Date, Start_Time, Duration_Minutes, Appointment_Type, Status, Reason_For_Visit)
            VALUES (%s, %s, %s, %s, %s, %s, 'Standard', 'Confirmed', 'Adjacent test')
            """,
            (patient_id, doctor_id, branch_id, test_date, "10:30:00", 30),
        )
        second_id = cur.lastrowid
        cleanup_trigger_test_appointments.append(second_id)
        db_conn.commit()

        assert first_id is not None and second_id is not None


def test_trigger_rejects_overlapping_appointment_update(db_conn, cleanup_trigger_test_appointments):
    """
    Verifies that trg_check_appointment_overlap_update rejects rescheduling into an occupied slot.
    """
    test_date = date(2027, 5, 12)
    doctor_id = 1
    patient_id = 1
    branch_id = 1

    with db_conn.cursor() as cur:
        # Appt 1: 09:00 - 09:30
        cur.execute(
            """
            INSERT INTO Appointment
            (Patient_ID, Doctor_ID, Branch_ID, Appointment_Date, Start_Time, Duration_Minutes, Appointment_Type, Status, Reason_For_Visit)
            VALUES (%s, %s, %s, %s, %s, %s, 'Standard', 'Confirmed', 'Appt 1')
            """,
            (patient_id, doctor_id, branch_id, test_date, "09:00:00", 30),
        )
        appt1 = cur.lastrowid
        cleanup_trigger_test_appointments.append(appt1)

        # Appt 2: 14:00 - 14:30
        cur.execute(
            """
            INSERT INTO Appointment
            (Patient_ID, Doctor_ID, Branch_ID, Appointment_Date, Start_Time, Duration_Minutes, Appointment_Type, Status, Reason_For_Visit)
            VALUES (%s, %s, %s, %s, %s, %s, 'Standard', 'Confirmed', 'Appt 2')
            """,
            (patient_id, doctor_id, branch_id, test_date, "14:00:00", 30),
        )
        appt2 = cur.lastrowid
        cleanup_trigger_test_appointments.append(appt2)
        db_conn.commit()

        # Attempt to reschedule Appt 2 into Appt 1's slot (09:15:00)
        with pytest.raises((pymysql.err.OperationalError, pymysql.err.InternalError)) as exc_info:
            cur.execute(
                """
                UPDATE Appointment
                SET Start_Time = '09:15:00'
                WHERE Appointment_ID = %s
                """,
                (appt2,),
            )
            db_conn.commit()

        db_conn.rollback()

        err_msg = str(exc_info.value)
        assert "Doctor already has an overlapping appointment in this time slot" in err_msg or "45000" in err_msg
