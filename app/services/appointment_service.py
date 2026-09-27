"""
Appointment service layer providing collision validation and scheduling utilities.
Ensures zero overlapping doctor appointments across both MySQL and TiDB Cloud environments.
"""

from datetime import date, time, timedelta, datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text


class AppointmentConflictError(Exception):
    """Raised when an appointment time slot collides with an existing booking."""
    def __init__(self, message: str = "Doctor already has an overlapping appointment in this time slot"):
        self.message = message
        super().__init__(self.message)


def compute_end_time(start: time, duration_minutes: int) -> time:
    """Computes end time given a starting time and duration in minutes."""
    dummy_date = date(2000, 1, 1)
    start_dt = datetime.combine(dummy_date, start)
    end_dt = start_dt + timedelta(minutes=duration_minutes)
    return end_dt.time()


def check_doctor_appointment_overlap(
    db: Session,
    doctor_id: int,
    appointment_date: date,
    start_time: time,
    duration_minutes: int,
    exclude_appointment_id: Optional[int] = None
) -> None:
    """
    Validates whether a doctor has any conflicting appointments on the given date and time range.
    Raises AppointmentConflictError if an overlap is detected.
    """
    end_time = compute_end_time(start_time, duration_minutes)

    query = """
        SELECT 
            Appointment_ID,
            Start_Time,
            ADDTIME(Start_Time, SEC_TO_TIME(Duration_Minutes * 60)) AS End_Time,
            Status
        FROM Appointment
        WHERE Doctor_ID = :doctor_id
          AND Appointment_Date = :appointment_date
          AND Status IN ('Scheduled', 'Confirmed', 'Completed')
          AND (
              (:new_start < ADDTIME(Start_Time, SEC_TO_TIME(Duration_Minutes * 60))) AND
              (:new_end > Start_Time)
          )
    """
    params = {
        "doctor_id": doctor_id,
        "appointment_date": appointment_date,
        "new_start": start_time.strftime("%H:%M:%S"),
        "new_end": end_time.strftime("%H:%M:%S")
    }

    if exclude_appointment_id is not None:
        query += " AND Appointment_ID != :exclude_id"
        params["exclude_id"] = exclude_appointment_id

    result = db.execute(text(query), params).fetchall()

    if result:
        conflicts = [f"ID {r[0]} ({r[1]} - {r[2]}, {r[3]})" for r in result]
        raise AppointmentConflictError(
            f"Doctor {doctor_id} already has an overlapping appointment on {appointment_date}: {', '.join(conflicts)}"
        )
