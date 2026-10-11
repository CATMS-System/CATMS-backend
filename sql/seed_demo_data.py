"""
Adds a few months of realistic demo data on top of 02_seed_data.sql:
40 patients, appointments from 60 days ago to 14 days ahead that fit the
doctors' shifts, and consultations, invoices and payments for past visits.
Run after run_all.py: python sql/seed_demo_data.py
Running it twice does nothing the second time.
"""
import random
from datetime import datetime, timedelta
from run_all import get_db_connection

FIRST_NAMES = ["Nimal", "Kamala", "Sunil", "Dilani", "Ruwan", "Ishara", "Chathura", "Nadeesha", "Pradeep", "Sanduni",
 "Tharindu", "Hiruni", "Kasun", "Malsha", "Lahiru", "Anjali", "Dinesh", "Piumi", "Sahan", "Thilini"]
LAST_NAMES = ["Perera", "Fernando", "Silva", "Jayasinghe", "Bandara", "Wickramasinghe", "Gunawardena", "Rajapaksa",
 "Herath", "Dissanayake"]
CITIES = [("Colombo", "Western Province", "00100"), ("Kandy", "Central Province", "20000"), ("Galle", "Southern Province",
"80000")]
REASONS = ["Fever and cough", "Routine checkup", "Back pain", "Skin rash", "Chest discomfort", "Headache", "Follow-up review",
 "Blood pressure check", "Allergy symptoms", "Stomach pain"]
DIAGNOSES = ["Viral fever", "Hypertension, stable", "Muscle strain", "Contact dermatitis", "Gastritis", "Migraine",
 "Seasonal allergy", "Healthy, no findings"]
METHODS = ["Cash", "Credit_Card", "Debit_Card", "Online"]
SLOT_MINUTES = 15


def to_time(value):
    # pymysql returns TIME columns as timedelta
    return (datetime.min + value).time() if isinstance(value, timedelta) else value


def main() -> None:
    random.seed(2026)
    conn = get_db_connection(include_database=True)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS n FROM Patient WHERE Email LIKE '%%@demo.catms.lk'")
            if cursor.fetchone()["n"] > 0:
                print("Demo data already loaded, nothing to do.")
                return
            # demo rows are not real user actions, so keep them out of the audit log
            cursor.execute("SET @audit_bypass = 1")
            cursor.execute("SELECT CURRENT_DATE AS today")
            today = cursor.fetchone()["today"]
            patient_ids = []
            for n in range(40):
                first, last = random.choice(FIRST_NAMES), random.choice(LAST_NAMES)
                city, province, postal = random.choice(CITIES)
                cursor.execute(
                    "INSERT INTO Patient (First_Name, Last_Name, Date_Of_Birth, Gender, NIC, Contact_Number, Email, "
                    "Street_Address, City, State_Province, Postal_Code, Registration_Date) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        first, last, today - timedelta(days=random.randint(18 * 365, 75 * 365)),
                        random.choice(["Male", "Female"]), f"19{random.randint(60, 99)}{n:08d}",
                        f"+9477{random.randint(1000000, 9999999)}", f"{first.lower()}.{last.lower()}{n}@demo.catms.lk",
                        f"{random.randint(1, 200)} Main Street", city, province, postal,
                        today - timedelta(days=random.randint(60, 400)),
                    ),
                )
                patient_id = cursor.lastrowid
                patient_ids.append(patient_id)
                cursor.execute(
                    "INSERT INTO Emergency_Contact (Patient_ID, First_Name, Last_Name, Relationship_To_Patient, Contact_Number) "
                    "VALUES (%s, %s, %s, 'Spouse', %s)",
                    (patient_id, random.choice(FIRST_NAMES), last, f"+9471{random.randint(1000000, 9999999)}"),
                )
            cursor.execute(
                "SELECT ds.Schedule_ID, ds.Doctor_ID, ds.Branch_ID, ds.Day_Of_Week, ds.Start_Time, ds.End_Time "
                "FROM Doctor_Schedule ds JOIN Staff s ON s.Staff_ID = ds.Doctor_ID "
                "WHERE ds.Availability_Status = 'Active' AND s.Employment_Status = 'Active'"
            )
            schedules = cursor.fetchall()
            counts = {"appointments": 0, "invoices": 0, "payments": 0}
            for offset in range(-60, 15):
                day = today + timedelta(days=offset)
                # each patient at most once a day, so no patient overlaps
                free_patients = random.sample(patient_ids, len(patient_ids))
                for schedule in schedules:
                    if schedule["Day_Of_Week"] != day.strftime("%A"):
                        continue
                    start = datetime.combine(day, to_time(schedule["Start_Time"]))
                    end = datetime.combine(day, to_time(schedule["End_Time"]))
                    slot = start
                    while slot + timedelta(minutes=SLOT_MINUTES) <= end and free_patients:
                        if random.random() < 0.45:
                            create_visit(cursor, schedule, day, slot.time(), free_patients.pop(), today, counts)
                        slot += timedelta(minutes=SLOT_MINUTES)
                # a couple of walk-ins on past weekdays
                if offset < 0 and day.weekday() < 6 and free_patients:
                    for schedule in [s for s in schedules if s["Day_Of_Week"] == day.strftime("%A")][:1]:
                        walk_in = schedule | {"Schedule_ID": None}
                        end_time = datetime.combine(day, to_time(schedule["End_Time"]))
                        create_visit(cursor, walk_in, day, end_time.time(), free_patients.pop(), today, counts, "Walk_In")
            cursor.execute("SET @audit_bypass = NULL")
            conn.commit()
            print(f"Added 40 patients, {counts['appointments']} appointments, {counts['invoices']} invoices, {counts['payments']} payments.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def create_visit(cursor, schedule, day, start_time, patient_id, today, counts, appointment_type=None):
    appointment_type = appointment_type or random.choice(["Standard", "Standard", "Standard", "Follow_Up"])
    if day < today:
        status = random.choices(["Completed", "Cancelled", "No_Show"], weights=[80, 12, 8])[0]
    elif day == today:
        status = random.choice(["Scheduled", "Confirmed", "Completed"])
    else:
        status = random.choice(["Scheduled", "Confirmed"])
    cursor.execute(
        "INSERT INTO Appointment (Patient_ID, Doctor_ID, Branch_ID, Schedule_ID, Appointment_Date, Start_Time, "
        "Duration_Minutes, Appointment_Type, Status, Cancellation_Reason, Reason_For_Visit) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (
            patient_id, schedule["Doctor_ID"], schedule["Branch_ID"], schedule["Schedule_ID"], day, start_time,
            SLOT_MINUTES, appointment_type, status, "Patient requested" if status == "Cancelled" else None,
            random.choice(REASONS),
        ),
    )
    appointment_id = cursor.lastrowid
    counts["appointments"] += 1
    if status != "Completed":
        return
    cursor.execute(
        "INSERT INTO Consultation (Appointment_ID, Consultation_Date, Diagnosis, Clinical_Notes) VALUES (%s, %s, %s, %s)",
        (appointment_id, day, random.choice(DIAGNOSES), "Seen and advised."),
    )
    consultation_id = cursor.lastrowid
    cursor.execute("SELECT Standard_Consultation_Fee AS fee FROM Doctor WHERE Doctor_ID = %s", (schedule["Doctor_ID"],))
    fee = cursor.fetchone()["fee"]
    # most bills are paid in full, some partly, some not yet
    paid = random.choices([fee, fee / 2, 0], weights=[75, 10, 15])[0]
    invoice_status = "Paid" if paid == fee else "Partially_Paid" if paid else "Issued"
    cursor.execute(
        "INSERT INTO Invoice (Consultation_ID, Invoice_Date, Billed_Consultation_Fee, Invoice_Status) VALUES (%s, %s, %s, %s)",
        (consultation_id, day, fee, invoice_status),
    )
    invoice_id = cursor.lastrowid
    counts["invoices"] += 1
    if paid:
        cursor.execute(
            "INSERT INTO Payment (Invoice_ID, Payment_Date, Amount, Payment_Method, Payment_Status, Transaction_Reference) "
            "VALUES (%s, %s, %s, %s, 'Completed', %s)",
            (invoice_id, day, paid, random.choice(METHODS), f"DEMO-{invoice_id:06d}"),
        )
        counts["payments"] += 1


if __name__ == "__main__":
    main()
