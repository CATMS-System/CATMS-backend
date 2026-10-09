import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import date, time
from app.db.connection import get_db_connection
from app.services.appointment_service import (
    book_appointment_atomic,
    AppointmentConflictError,
    AppointmentValidationError,
)


def main():
    conn = get_db_connection()
    created_ids = []

    print("=== Running Day 3: Atomic Booking Transaction Tests (Option C) ===")

    try:
        # Test 1: Successful Atomic Booking
        print("\n--- Test 1: Successful Atomic Booking ---")
        test_date = date(2026, 9, 15)
        test_time = time(14, 0)  # 14:00 - 14:30
        booking = book_appointment_atomic(
            conn=conn,
            patient_id=1,
            doctor_id=1,
            branch_id=1,
            appointment_date=test_date,
            start_time=test_time,
            duration_minutes=30,
            appointment_type="Standard",
            reason_for_visit="Routine Cardiology Follow-up"
        )

        assert booking is not None
        assert booking["Appointment_ID"] > 0
        assert booking["Patient_Name"] == "John Doe"
        assert booking["Doctor_Name"] == "Alexander Bennett"
        assert booking["Branch_Name"] == "Colombo Main Clinic"
        assert booking["Status"] == "Scheduled"
        created_ids.append(booking["Appointment_ID"])
        print(f"PASSED: Appointment #{booking['Appointment_ID']} created atomically.")
        print(f"Details: Patient={booking['Patient_Name']}, Doctor={booking['Doctor_Name']}, Time={booking['Start_Time']}-{booking['End_Time']}")

        # Test 2: Overlapping Booking Collision Rollback
        print("\n--- Test 2: Overlapping Slot Collision Rejection ---")
        # Candidate slot: 14:15 - 14:45 overlaps with 14:00 - 14:30
        try:
            book_appointment_atomic(
                conn=conn,
                patient_id=2,
                doctor_id=1,
                branch_id=1,
                appointment_date=test_date,
                start_time=time(14, 15),
                duration_minutes=30,
                appointment_type="Standard",
                reason_for_visit="Emergency Consultation"
            )
            print("FAILED: Overlapping booking was incorrectly allowed!")
            assert False, "Should have raised AppointmentConflictError"
        except AppointmentConflictError as exc:
            print(f"PASSED: Overlapping slot correctly rejected: {exc}")

        # Test 3: Validation Error on Non-existent Patient
        print("\n--- Test 3: Validation Error on Non-existent Patient ---")
        try:
            book_appointment_atomic(
                conn=conn,
                patient_id=999999,
                doctor_id=1,
                branch_id=1,
                appointment_date=test_date,
                start_time=time(15, 0),
                duration_minutes=15,
                appointment_type="Standard",
                reason_for_visit="General Checkup"
            )
            print("FAILED: Non-existent patient was allowed!")
            assert False, "Should have raised AppointmentValidationError"
        except AppointmentValidationError as exc:
            print(f"PASSED: Non-existent patient correctly blocked: {exc}")

        # Test 4: Validation Error on Invalid Appointment Type
        print("\n--- Test 4: Validation Error on Invalid Type ---")
        try:
            book_appointment_atomic(
                conn=conn,
                patient_id=1,
                doctor_id=1,
                branch_id=1,
                appointment_date=test_date,
                start_time=time(15, 0),
                duration_minutes=15,
                appointment_type="InvalidType",
                reason_for_visit="Test"
            )
            print("FAILED: Invalid appointment type was allowed!")
            assert False, "Should have raised AppointmentValidationError"
        except AppointmentValidationError as exc:
            print(f"PASSED: Invalid type rejected: {exc}")

    finally:
        # Cleanup created test appointments to keep database clean
        if created_ids:
            print("\n--- Cleaning up test records ---")
            with conn.cursor() as cursor:
                for appt_id in created_ids:
                    cursor.execute("DELETE FROM Appointment WHERE Appointment_ID = %s", (appt_id,))
                    print(f"Deleted test appointment #{appt_id}")
            conn.commit()
        conn.close()

    print("\n=== All Day 3 Atomic Booking Tests Completed Successfully ===")


if __name__ == "__main__":
    main()

