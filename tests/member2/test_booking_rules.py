# bookings must match the doctor's shift, not be in the past,
# and not be made for a doctor who is not working
from datetime import date, timedelta
import pytest
from app.services.appointment_service import AppointmentValidationError, book_appointment_atomic


def next_day(day_name):
    day = date.today() + timedelta(days=1)
    while day.strftime("%A") != day_name:
        day += timedelta(days=1)
    return day


def book(db, **changes):
    values = {
        "patient_id": 1,
        "doctor_id": 1,
        "branch_id": 1,
        "appointment_date": next_day("Monday"),  # doctor 1 works Monday 08:30-13:00 at branch 1
        "start_time": "09:00:00",
        "duration_minutes": 15,
        "appointment_type": "Standard",
        "reason_for_visit": "booking rules test",
    }
    values.update(changes)
    return book_appointment_atomic(conn=db, **values)


@pytest.fixture
def booked(db):
    ids = []
    yield ids
    with db.cursor() as cursor:
        for appointment_id in ids:
            cursor.execute("DELETE FROM Appointment WHERE Appointment_ID = %s", (appointment_id,))
        db.commit()


def test_booking_inside_shift_works(db, booked):
    appointment = book(db, start_time="12:30:00")
    booked.append(appointment["Appointment_ID"])
    assert appointment["Schedule_ID"] == 1


def test_booking_outside_shift_is_refused(db):
    with pytest.raises(AppointmentValidationError, match="no shift"):
        book(db, appointment_date=next_day("Sunday"))
    with pytest.raises(AppointmentValidationError, match="no shift"):
        book(db, start_time="12:50:00")  # ends 13:05, after the shift
    with pytest.raises(AppointmentValidationError, match="no shift"):
        book(db, schedule_id=7)  # schedule 7 is doctor 8's shift in Galle


def test_booking_in_the_past_is_refused(db):
    with pytest.raises(AppointmentValidationError, match="past date"):
        book(db, appointment_date=date(2020, 1, 6))


def test_booking_doctor_on_leave_is_refused(db):
    with db.cursor() as cursor:
        cursor.execute("UPDATE Staff SET Employment_Status = 'On_Leave' WHERE Staff_ID = 1")
    db.commit()
    try:
        with pytest.raises(AppointmentValidationError, match="not available"):
            book(db)
    finally:
        with db.cursor() as cursor:
            cursor.execute("UPDATE Staff SET Employment_Status = 'Active' WHERE Staff_ID = 1")
        db.commit()
