"""
Appointment service layer providing collision validation, atomic booking, and scheduling utilities.
Ensures zero overlapping doctor appointments across both MySQL and TiDB Cloud environments.
Built using Option C (Plain PyMySQL).
"""

from datetime import date, time, timedelta, datetime
from typing import Optional, Dict, Any
import pymysql
import pymysql.cursors


class AppointmentConflictError(Exception):
    """Raised when an appointment time slot collides with an existing booking."""
    def __init__(self, message: str = "Doctor already has an overlapping appointment in this time slot"):
        self.message = message
        super().__init__(self.message)


class AppointmentValidationError(Exception):
    """Raised when appointment input validation or foreign key checks fail."""
    def __init__(self, message: str):
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
        start_time.strftime("%H:%M:%S") if isinstance(start_time, time) else start_time,
        end_time.strftime("%H:%M:%S") if isinstance(end_time, time) else end_time
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


def book_appointment_atomic(
    conn: pymysql.Connection,
    patient_id: int,
    doctor_id: int,
    branch_id: int,
    appointment_date: date,
    start_time: time,
    duration_minutes: int = 15,
    appointment_type: str = "Standard",
    reason_for_visit: str = "General Consultation",
    schedule_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Atomically creates a new appointment record with transactional integrity (ACID).
    Validates patient, doctor, branch presence and performs collision check.
    Rolls back transaction on any error.
    """
    # 1. Validation of required inputs
    valid_types = ("Standard", "Follow_Up", "Emergency", "Walk_In")
    if appointment_type not in valid_types:
        raise AppointmentValidationError(
            f"Invalid appointment type '{appointment_type}'. Must be one of: {', '.join(valid_types)}"
        )

    if duration_minutes <= 0:
        raise AppointmentValidationError("Duration must be a positive integer in minutes.")

    # 2. Foreign Key existence checks
    with conn.cursor() as cursor:
        cursor.execute("SELECT Patient_ID FROM Patient WHERE Patient_ID = %s", (patient_id,))
        if not cursor.fetchone():
            raise AppointmentValidationError(f"Patient with ID {patient_id} does not exist.")

        cursor.execute("SELECT Doctor_ID FROM Doctor WHERE Doctor_ID = %s", (doctor_id,))
        if not cursor.fetchone():
            raise AppointmentValidationError(f"Doctor with ID {doctor_id} does not exist.")

        cursor.execute("SELECT Branch_ID FROM Branch WHERE Branch_ID = %s", (branch_id,))
        if not cursor.fetchone():
            raise AppointmentValidationError(f"Branch with ID {branch_id} does not exist.")

        if schedule_id is not None:
            cursor.execute("SELECT Schedule_ID FROM Doctor_Schedule WHERE Schedule_ID = %s", (schedule_id,))
            if not cursor.fetchone():
                raise AppointmentValidationError(f"Doctor schedule with ID {schedule_id} does not exist.")

    # 3. Collision check
    check_doctor_appointment_overlap(
        conn=conn,
        doctor_id=doctor_id,
        appointment_date=appointment_date,
        start_time=start_time,
        duration_minutes=duration_minutes
    )

    # 4. Atomic Transaction Execution
    status = "Confirmed" if appointment_type == "Walk_In" else "Scheduled"
    time_str = start_time.strftime("%H:%M:%S") if isinstance(start_time, time) else start_time

    insert_sql = """
        INSERT INTO Appointment (
            Patient_ID, Doctor_ID, Branch_ID, Schedule_ID,
            Appointment_Date, Start_Time, Duration_Minutes,
            Appointment_Type, Status, Reason_For_Visit
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    try:
        with conn.cursor() as cursor:
            cursor.execute(insert_sql, (
                patient_id,
                doctor_id,
                branch_id,
                schedule_id,
                appointment_date,
                time_str,
                duration_minutes,
                appointment_type,
                status,
                reason_for_visit
            ))
            appointment_id = cursor.lastrowid
        conn.commit()
    except Exception as exc:
        conn.rollback()
        raise exc

    # 5. Fetch and return complete created record with joins
    fetch_sql = """
        SELECT 
            a.Appointment_ID,
            a.Patient_ID,
            CONCAT(p.First_Name, ' ', p.Last_Name) AS Patient_Name,
            p.NIC AS Patient_NIC,
            p.Contact_Number AS Patient_Phone,
            a.Doctor_ID,
            CONCAT(s.First_Name, ' ', s.Last_Name) AS Doctor_Name,
            a.Branch_ID,
            b.Branch_Name,
            a.Schedule_ID,
            a.Appointment_Date,
            a.Start_Time,
            a.Duration_Minutes,
            ADDTIME(a.Start_Time, SEC_TO_TIME(a.Duration_Minutes * 60)) AS End_Time,
            a.Appointment_Type,
            a.Status,
            a.Reason_For_Visit,
            a.Created_At
        FROM Appointment a
        JOIN Patient p ON a.Patient_ID = p.Patient_ID
        JOIN Doctor d ON a.Doctor_ID = d.Doctor_ID
        JOIN Staff s ON d.Doctor_ID = s.Staff_ID
        JOIN Branch b ON a.Branch_ID = b.Branch_ID
        WHERE a.Appointment_ID = %s
    """
    with conn.cursor() as cursor:
        cursor.execute(fetch_sql, (appointment_id,))
        created_record = cursor.fetchone()

    return created_record


def get_appointment_by_id(conn: pymysql.Connection, appointment_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieves a single appointment by its primary key with complete joined relations.
    Returns None if the appointment record does not exist.
    """
    sql = """
        SELECT 
            a.Appointment_ID,
            a.Patient_ID,
            CONCAT(p.First_Name, ' ', p.Last_Name) AS Patient_Name,
            p.NIC AS Patient_NIC,
            p.Contact_Number AS Patient_Phone,
            p.Gender AS Patient_Gender,
            a.Doctor_ID,
            CONCAT(s.First_Name, ' ', s.Last_Name) AS Doctor_Name,
            d.License_Number AS Doctor_License,
            a.Branch_ID,
            b.Branch_Name,
            b.City AS Branch_City,
            a.Schedule_ID,
            a.Appointment_Date,
            a.Start_Time,
            a.Duration_Minutes,
            ADDTIME(a.Start_Time, SEC_TO_TIME(a.Duration_Minutes * 60)) AS End_Time,
            a.Appointment_Type,
            a.Status,
            a.Cancellation_Reason,
            a.Reason_For_Visit,
            a.Created_At
        FROM Appointment a
        JOIN Patient p ON a.Patient_ID = p.Patient_ID
        JOIN Doctor d ON a.Doctor_ID = d.Doctor_ID
        JOIN Staff s ON d.Doctor_ID = s.Staff_ID
        JOIN Branch b ON a.Branch_ID = b.Branch_ID
        WHERE a.Appointment_ID = %s
    """
    with conn.cursor() as cursor:
        cursor.execute(sql, (appointment_id,))
        return cursor.fetchone()


def get_appointments_by_date(
    conn: pymysql.Connection,
    doctor_id: Optional[int] = None,
    branch_id: Optional[int] = None,
    appointment_date: Optional[date] = None,
    status: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retrieves appointments matching multi-criteria filters (doctor, branch, date, status).
    Orders records by Appointment_Date and Start_Time for clinic queue tracking.
    """
    sql = """
        SELECT 
            a.Appointment_ID,
            a.Patient_ID,
            CONCAT(p.First_Name, ' ', p.Last_Name) AS Patient_Name,
            p.NIC AS Patient_NIC,
            p.Contact_Number AS Patient_Phone,
            a.Doctor_ID,
            CONCAT(s.First_Name, ' ', s.Last_Name) AS Doctor_Name,
            a.Branch_ID,
            b.Branch_Name,
            a.Schedule_ID,
            a.Appointment_Date,
            a.Start_Time,
            a.Duration_Minutes,
            ADDTIME(a.Start_Time, SEC_TO_TIME(a.Duration_Minutes * 60)) AS End_Time,
            a.Appointment_Type,
            a.Status,
            a.Cancellation_Reason,
            a.Reason_For_Visit,
            a.Created_At
        FROM Appointment a
        JOIN Patient p ON a.Patient_ID = p.Patient_ID
        JOIN Doctor d ON a.Doctor_ID = d.Doctor_ID
        JOIN Staff s ON d.Doctor_ID = s.Staff_ID
        JOIN Branch b ON a.Branch_ID = b.Branch_ID
    """
    where_clauses = []
    params = []

    if doctor_id is not None:
        where_clauses.append("a.Doctor_ID = %s")
        params.append(doctor_id)

    if branch_id is not None:
        where_clauses.append("a.Branch_ID = %s")
        params.append(branch_id)

    if appointment_date is not None:
        where_clauses.append("a.Appointment_Date = %s")
        params.append(appointment_date)

    if status is not None:
        where_clauses.append("a.Status = %s")
        params.append(status)

    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)

    sql += " ORDER BY a.Appointment_Date ASC, a.Start_Time ASC"

    with conn.cursor() as cursor:
        cursor.execute(sql, tuple(params))
        return cursor.fetchall()


def get_appointment_status_counts(
    conn: pymysql.Connection,
    branch_id: Optional[int] = None,
    appointment_date: Optional[date] = None,
    doctor_id: Optional[int] = None
) -> Dict[str, int]:
    """
    Aggregates appointment status metrics for daily clinic operational oversight.
    Returns counts for Total, Scheduled, Confirmed, Completed, Cancelled, No_Show, and Walk_In.
    """
    sql = """
        SELECT 
            COUNT(*) AS Total,
            COALESCE(SUM(CASE WHEN Status = 'Scheduled' THEN 1 ELSE 0 END), 0) AS Scheduled,
            COALESCE(SUM(CASE WHEN Status = 'Confirmed' THEN 1 ELSE 0 END), 0) AS Confirmed,
            COALESCE(SUM(CASE WHEN Status = 'Completed' THEN 1 ELSE 0 END), 0) AS Completed,
            COALESCE(SUM(CASE WHEN Status = 'Cancelled' THEN 1 ELSE 0 END), 0) AS Cancelled,
            COALESCE(SUM(CASE WHEN Status = 'No_Show' THEN 1 ELSE 0 END), 0) AS No_Show,
            COALESCE(SUM(CASE WHEN Appointment_Type = 'Walk_In' THEN 1 ELSE 0 END), 0) AS Walk_In
        FROM Appointment
    """
    where_clauses = []
    params = []

    if branch_id is not None:
        where_clauses.append("Branch_ID = %s")
        params.append(branch_id)

    if appointment_date is not None:
        where_clauses.append("Appointment_Date = %s")
        params.append(appointment_date)

    if doctor_id is not None:
        where_clauses.append("Doctor_ID = %s")
        params.append(doctor_id)

    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)

    with conn.cursor() as cursor:
        cursor.execute(sql, tuple(params))
        row = cursor.fetchone()

    return {
        "Total": int(row["Total"]),
        "Scheduled": int(row["Scheduled"]),
        "Confirmed": int(row["Confirmed"]),
        "Completed": int(row["Completed"]),
        "Cancelled": int(row["Cancelled"]),
        "No_Show": int(row["No_Show"]),
        "Walk_In": int(row["Walk_In"]),
    }

