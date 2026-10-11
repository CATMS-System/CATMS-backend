"""
Doctor and Specialty service layer for Option C (Plain PyMySQL).
Provides query functions and business logic for medical specialties,
doctor directory, and physician profiles with relational joins.
"""

from typing import Optional, List, Dict, Any
import pymysql
import pymysql.cursors


class DoctorNotFoundError(Exception):
    """Raised when a doctor with the specified ID cannot be found."""
    def __init__(self, doctor_id: int):
        self.doctor_id = doctor_id
        super().__init__(f"Doctor with ID {doctor_id} not found.")


def get_all_specialties(conn: pymysql.Connection) -> List[Dict[str, Any]]:
    """
    Retrieves all registered medical specialties with doctor counts.
    """
    query = """
        SELECT 
            s.Specialty_ID,
            s.Specialty_Name,
            s.Description,
            COUNT(ds.Doctor_ID) AS Doctor_Count
        FROM Specialty s
        LEFT JOIN Doctor_Specialty ds ON s.Specialty_ID = ds.Specialty_ID
        GROUP BY s.Specialty_ID, s.Specialty_Name, s.Description
        ORDER BY s.Specialty_Name ASC
    """
    with conn.cursor() as cursor:
        cursor.execute(query)
        return cursor.fetchall()


def get_doctor_specialties(conn: pymysql.Connection, doctor_id: int) -> List[Dict[str, Any]]:
    """
    Retrieves the list of specialties assigned to a specific doctor.
    """
    query = """
        SELECT 
            s.Specialty_ID,
            s.Specialty_Name,
            s.Description
        FROM Specialty s
        JOIN Doctor_Specialty ds ON s.Specialty_ID = ds.Specialty_ID
        WHERE ds.Doctor_ID = %s
        ORDER BY s.Specialty_Name ASC
    """
    with conn.cursor() as cursor:
        cursor.execute(query, (doctor_id,))
        return cursor.fetchall()


def get_all_doctors(
    conn: pymysql.Connection,
    branch_id: Optional[int] = None,
    specialty_id: Optional[int] = None,
    search: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retrieves doctors matching optional filters (branch, specialty, name/license search).
    Includes joined staff details, home branch information, and aggregated specialties.
    """
    query = """
        SELECT 
            d.Doctor_ID,
            s.Staff_ID,
            s.First_Name,
            s.Last_Name,
            CONCAT(s.First_Name, ' ', s.Last_Name) AS Full_Name,
            s.Email,
            s.Contact_Number,
            s.Employment_Status,
            b.Branch_ID,
            b.Branch_Name,
            b.City AS Branch_City,
            d.License_Number,
            d.Standard_Consultation_Fee,
            COALESCE(
                GROUP_CONCAT(DISTINCT spec.Specialty_Name ORDER BY spec.Specialty_Name SEPARATOR ', '),
                'General Practice'
            ) AS Specialties,
            COALESCE(
                GROUP_CONCAT(DISTINCT spec.Specialty_ID ORDER BY spec.Specialty_ID SEPARATOR ','),
                ''
            ) AS Specialty_IDs
        FROM Doctor d
        JOIN Staff s ON d.Doctor_ID = s.Staff_ID
        JOIN Branch b ON s.Branch_ID = b.Branch_ID
        LEFT JOIN Doctor_Specialty ds ON d.Doctor_ID = ds.Doctor_ID
        LEFT JOIN Specialty spec ON ds.Specialty_ID = spec.Specialty_ID
    """
    where_clauses = []
    params = []

    if branch_id is not None:
        where_clauses.append("s.Branch_ID = %s")
        params.append(branch_id)

    if search:
        search_pattern = f"%{search.strip()}%"
        where_clauses.append(
            "(s.First_Name LIKE %s OR s.Last_Name LIKE %s OR d.License_Number LIKE %s)"
        )
        params.extend([search_pattern, search_pattern, search_pattern])

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    query += """
        GROUP BY 
            d.Doctor_ID, s.Staff_ID, s.First_Name, s.Last_Name, s.Email, 
            s.Contact_Number, s.Employment_Status, b.Branch_ID, b.Branch_Name, 
            b.City, d.License_Number, d.Standard_Consultation_Fee
    """

    if specialty_id is not None:
        query += " HAVING FIND_IN_SET(%s, Specialty_IDs) > 0"
        params.append(str(specialty_id))

    query += " ORDER BY s.Last_Name ASC, s.First_Name ASC"

    with conn.cursor() as cursor:
        cursor.execute(query, tuple(params))
        doctors = cursor.fetchall()

    return doctors


def get_doctor_by_id(conn: pymysql.Connection, doctor_id: int) -> Dict[str, Any]:
    """
    Retrieves full profile of a single doctor by Doctor_ID,
    including detailed list of assigned specialties.
    Raises DoctorNotFoundError if the doctor does not exist.
    """
    query = """
        SELECT 
            d.Doctor_ID,
            s.Staff_ID,
            s.First_Name,
            s.Last_Name,
            CONCAT(s.First_Name, ' ', s.Last_Name) AS Full_Name,
            s.Email,
            s.Contact_Number,
            s.Employment_Status,
            b.Branch_ID,
            b.Branch_Name,
            b.City AS Branch_City,
            b.Street_Address AS Branch_Address,
            d.License_Number,
            d.Standard_Consultation_Fee
        FROM Doctor d
        JOIN Staff s ON d.Doctor_ID = s.Staff_ID
        JOIN Branch b ON s.Branch_ID = b.Branch_ID
        WHERE d.Doctor_ID = %s
    """
    with conn.cursor() as cursor:
        cursor.execute(query, (doctor_id,))
        doctor = cursor.fetchone()

    if not doctor:
        raise DoctorNotFoundError(doctor_id)

    # Attach assigned specialties as a structured list
    doctor["Specialties"] = get_doctor_specialties(conn, doctor_id)
    return doctor


def format_time_value(val: Any) -> str:
    """Helper to convert time or timedelta to HH:MM:SS string."""
    from datetime import timedelta, time as dt_time
    if isinstance(val, timedelta):
        total_seconds = int(val.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    elif isinstance(val, dt_time):
        return val.strftime("%H:%M:%S")
    return str(val) if val is not None else ""


def get_doctor_schedules(
    conn: pymysql.Connection,
    doctor_id: int,
    branch_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Retrieves weekly schedule blocks for a doctor, ordered by weekday.
    Joins with Branch to indicate clinic practicing location.
    """
    query = """
        SELECT 
            ds.Schedule_ID,
            ds.Doctor_ID,
            ds.Branch_ID,
            b.Branch_Name,
            b.City AS Branch_City,
            ds.Day_Of_Week,
            ds.Start_Time,
            ds.End_Time,
            ROUND(TIME_TO_SEC(TIMEDIFF(ds.End_Time, ds.Start_Time)) / 60) AS Shift_Duration_Minutes,
            ds.Availability_Status
        FROM Doctor_Schedule ds
        JOIN Branch b ON ds.Branch_ID = b.Branch_ID
        WHERE ds.Doctor_ID = %s
    """
    params = [doctor_id]
    if branch_id is not None:
        query += " AND ds.Branch_ID = %s"
        params.append(branch_id)

    query += " ORDER BY FIELD(ds.Day_Of_Week, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'), ds.Start_Time ASC"

    with conn.cursor() as cursor:
        cursor.execute(query, tuple(params))
        schedules = cursor.fetchall()

    for s in schedules:
        s["Start_Time_Str"] = format_time_value(s["Start_Time"])
        s["End_Time_Str"] = format_time_value(s["End_Time"])
        s["Start_Time"] = s["Start_Time_Str"]
        s["End_Time"] = s["End_Time_Str"]

    return schedules


class ScheduleNotFoundError(Exception):
    def __init__(self, schedule_id: int):
        self.schedule_id = schedule_id
        super().__init__(f"Doctor schedule with ID {schedule_id} does not exist.")


class ScheduleConflictError(Exception):
    def __init__(self, message: str = "Doctor already has a schedule shift overlapping with this time interval."):
        self.message = message
        super().__init__(self.message)


class ScheduleValidationError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


def normalize_schedule_time(val: Any) -> str:
    """Normalizes time or string input to HH:MM:SS format."""
    if isinstance(val, str):
        val = val.strip()
        parts = val.split(":")
        if len(parts) == 2:
            return f"{int(parts[0]):02d}:{int(parts[1]):02d}:00"
        elif len(parts) == 3:
            return f"{int(parts[0]):02d}:{int(parts[1]):02d}:{int(parts[2]):02d}"
        raise ScheduleValidationError(f"Invalid time format: {val}")
    elif hasattr(val, "strftime"):
        return val.strftime("%H:%M:%S")
    raise ScheduleValidationError(f"Invalid time value: {val}")


def get_schedule_by_id(conn: pymysql.Connection, schedule_id: int) -> Dict[str, Any]:
    query = """
        SELECT 
            ds.Schedule_ID,
            ds.Doctor_ID,
            ds.Branch_ID,
            b.Branch_Name,
            b.City AS Branch_City,
            ds.Day_Of_Week,
            ds.Start_Time,
            ds.End_Time,
            ROUND(TIME_TO_SEC(TIMEDIFF(ds.End_Time, ds.Start_Time)) / 60) AS Shift_Duration_Minutes,
            ds.Availability_Status
        FROM Doctor_Schedule ds
        JOIN Branch b ON ds.Branch_ID = b.Branch_ID
        WHERE ds.Schedule_ID = %s
    """
    with conn.cursor() as cursor:
        cursor.execute(query, (schedule_id,))
        schedule = cursor.fetchone()

    if not schedule:
        raise ScheduleNotFoundError(schedule_id)

    schedule["Start_Time_Str"] = format_time_value(schedule["Start_Time"])
    schedule["End_Time_Str"] = format_time_value(schedule["End_Time"])
    schedule["Start_Time"] = schedule["Start_Time_Str"]
    schedule["End_Time"] = schedule["End_Time_Str"]
    return schedule


def check_schedule_overlap(
    conn: pymysql.Connection,
    doctor_id: int,
    day_of_week: str,
    start_time_str: str,
    end_time_str: str,
    exclude_schedule_id: Optional[int] = None
) -> None:
    query = """
        SELECT Schedule_ID, Start_Time, End_Time
        FROM Doctor_Schedule
        WHERE Doctor_ID = %s
          AND Day_Of_Week = %s
          AND (%s < End_Time AND %s > Start_Time)
    """
    params = [doctor_id, day_of_week, start_time_str, end_time_str]
    if exclude_schedule_id is not None:
        query += " AND Schedule_ID != %s"
        params.append(exclude_schedule_id)

    with conn.cursor() as cursor:
        cursor.execute(query, tuple(params))
        conflict = cursor.fetchone()
        if conflict:
            raise ScheduleConflictError(
                f"Doctor already has a shift on {day_of_week} overlapping with {start_time_str} - {end_time_str}."
            )


def create_doctor_schedule(
    conn: pymysql.Connection,
    doctor_id: int,
    branch_id: int,
    day_of_week: str,
    start_time: str,
    end_time: str,
    availability_status: str = "Active"
) -> Dict[str, Any]:
    norm_start = normalize_schedule_time(start_time)
    norm_end = normalize_schedule_time(end_time)

    if norm_start >= norm_end:
        raise ScheduleValidationError("Start time must be strictly before end time.")

    with conn.cursor() as cursor:
        cursor.execute("SELECT Doctor_ID FROM Doctor WHERE Doctor_ID = %s", (doctor_id,))
        if not cursor.fetchone():
            raise DoctorNotFoundError(doctor_id)

        cursor.execute("SELECT Branch_ID FROM Branch WHERE Branch_ID = %s", (branch_id,))
        if not cursor.fetchone():
            raise ScheduleValidationError(f"Branch with ID {branch_id} does not exist.")

    check_schedule_overlap(conn, doctor_id, day_of_week, norm_start, norm_end)

    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO Doctor_Schedule 
            (Doctor_ID, Branch_ID, Day_Of_Week, Start_Time, End_Time, Availability_Status)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (doctor_id, branch_id, day_of_week, norm_start, norm_end, availability_status)
        )
        schedule_id = cursor.lastrowid
        conn.commit()

    return get_schedule_by_id(conn, schedule_id)


def update_doctor_schedule(
    conn: pymysql.Connection,
    schedule_id: int,
    branch_id: Optional[int] = None,
    day_of_week: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    availability_status: Optional[str] = None
) -> Dict[str, Any]:
    existing = get_schedule_by_id(conn, schedule_id)
    doctor_id = existing["Doctor_ID"]

    eff_branch_id = branch_id if branch_id is not None else existing["Branch_ID"]
    eff_day = day_of_week if day_of_week is not None else existing["Day_Of_Week"]
    eff_start = normalize_schedule_time(start_time) if start_time is not None else existing["Start_Time_Str"]
    eff_end = normalize_schedule_time(end_time) if end_time is not None else existing["End_Time_Str"]
    eff_status = availability_status if availability_status is not None else existing["Availability_Status"]

    if eff_start >= eff_end:
        raise ScheduleValidationError("Start time must be strictly before end time.")

    if branch_id is not None:
        with conn.cursor() as cursor:
            cursor.execute("SELECT Branch_ID FROM Branch WHERE Branch_ID = %s", (branch_id,))
            if not cursor.fetchone():
                raise ScheduleValidationError(f"Branch with ID {branch_id} does not exist.")

    check_schedule_overlap(conn, doctor_id, eff_day, eff_start, eff_end, exclude_schedule_id=schedule_id)

    with conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE Doctor_Schedule
            SET Branch_ID = %s, Day_Of_Week = %s, Start_Time = %s, End_Time = %s, Availability_Status = %s
            WHERE Schedule_ID = %s
            """,
            (eff_branch_id, eff_day, eff_start, eff_end, eff_status, schedule_id)
        )
        conn.commit()

    return get_schedule_by_id(conn, schedule_id)

