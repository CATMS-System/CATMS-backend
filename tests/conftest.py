# shared fixtures for the backend tests
import pytest
from app.db.connection import get_db_connection

DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


# booking now needs a matching doctor shift, so appointment tests that book
# doctor 1 at branch 1 on any day and time get an all-day shift for every day
@pytest.fixture(scope="module")
def open_schedule_for_doctor_1():
    conn = get_db_connection()
    schedule_ids = []
    try:
        with conn.cursor() as cursor:
            for day in DAYS:
                cursor.execute(
                    "INSERT INTO Doctor_Schedule (Doctor_ID, Branch_ID, Day_Of_Week, Start_Time, End_Time, "
                    "Availability_Status) VALUES (1, 1, %s, '00:00:00', '23:59:59', 'Active')",
                    (day,),
                )
                schedule_ids.append(cursor.lastrowid)
        conn.commit()
        yield
    finally:
        with conn.cursor() as cursor:
            for schedule_id in schedule_ids:
                cursor.execute("UPDATE Appointment SET Schedule_ID = NULL WHERE Schedule_ID = %s", (schedule_id,))
                cursor.execute("DELETE FROM Doctor_Schedule WHERE Schedule_ID = %s", (schedule_id,))
        conn.commit()
        conn.close()
