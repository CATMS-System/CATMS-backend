"""
Appointment service layer providing collision validation and scheduling utilities.
Ensures zero overlapping doctor appointments across both MySQL and TiDB Cloud environments.
Built using Option C (Plain PyMySQL).
"""

from datetime import date, time, timedelta, datetime
from typing import Optional
import pymysql
import pymysql.cursors


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
    conn: pymysql.Connection,
    doctor_id: int,
    appointment_date: date,
    start_time: time,
    duration_minutes: int,
    exclude_appointment_id: Optional[int] = None
) -> None:
    """
    Validates whether a doctor has any conflicting appointments on the given date and time range.
    Uses Option C (Plain PyMySQL with DictCursor).
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
        WHERE Doctor_ID = %s
          AND Appointment_Date = %s
          AND Status IN ('Scheduled', 'Confirmed', 'Completed')
          AND (
              (%s < ADDTIME(Start_Time, SEC_TO_TIME(Duration_Minutes * 60))) AND
              (%s > Start_Time)
          )
    """
    params = [
        doctor_id,
        appointment_date,
        start_time.strftime("%H:%M:%S"),
        end_time.strftime("%H:%M:%S")
    ]

    if exclude_appointment_id is not None:
        query += " AND Appointment_ID != %s"
        params.append(exclude_appointment_id)

    with conn.cursor() as cursor:
        cursor.execute(query, tuple(params))
        result = cursor.fetchall()

    if result:
        conflicts = [
            f"ID {r['Appointment_ID']} ({r['Start_Time']} - {r['End_Time']}, {r['Status']})"
            if isinstance(r, dict) else f"ID {r[0]} ({r[1]} - {r[2]}, {r[3]})"
            for r in result
        ]
        raise AppointmentConflictError(
            f"Doctor {doctor_id} already has an overlapping appointment on {appointment_date}: {', '.join(conflicts)}"
        )
