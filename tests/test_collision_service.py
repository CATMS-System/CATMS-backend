import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import certifi
from datetime import date, time
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.services.appointment_service import check_doctor_appointment_overlap, AppointmentConflictError

load_dotenv()

user = os.getenv("DB_USER")
pwd = os.getenv("DB_PASSWORD")
host = os.getenv("DB_HOST")
port = os.getenv("DB_PORT")
dbname = os.getenv("DB_NAME")

url = f"mysql+pymysql://{user}:{pwd}@{host}:{port}/{dbname}"
engine = create_engine(url, connect_args={"ssl": {"ca": certifi.where()}})
Session = sessionmaker(bind=engine)
db = Session()

print("--- Running Appointment Collision Validation Tests ---")

# Test 1: Doctor 1 on 2026-08-23 has an appointment 09:00 - 09:30.
# A candidate slot at 09:15 - 09:30 MUST fail.
try:
    check_doctor_appointment_overlap(
        db,
        doctor_id=1,
        appointment_date=date(2026, 8, 23),
        start_time=time(9, 15),
        duration_minutes=15
    )
    print("FAILED: Test 1 overlap was not detected!")
except AppointmentConflictError as e:
    print(f"PASSED: Test 1 overlap correctly detected -> {e}")

# Test 2: Slot 09:30 - 10:00 is immediately adjacent, not overlapping.
try:
    check_doctor_appointment_overlap(
        db,
        doctor_id=1,
        appointment_date=date(2026, 8, 23),
        start_time=time(9, 30),
        duration_minutes=30
    )
    print("PASSED: Test 2 adjacent slot (09:30 - 10:00) accepted without conflict.")
except AppointmentConflictError as e:
    print(f"FAILED: Test 2 threw unexpected conflict -> {e}")

# Test 3: Rescheduling Appointment 1 at the same slot with exclude_appointment_id=1.
try:
    check_doctor_appointment_overlap(
        db,
        doctor_id=1,
        appointment_date=date(2026, 8, 23),
        start_time=time(9, 0),
        duration_minutes=30,
        exclude_appointment_id=1
    )
    print("PASSED: Test 3 self-exclusion during reschedule accepted.")
except AppointmentConflictError as e:
    print(f"FAILED: Test 3 threw unexpected conflict -> {e}")

db.close()
print("--- All Collision Validation Tests Completed Successfully ---")
