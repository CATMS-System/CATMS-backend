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

    return schedules

