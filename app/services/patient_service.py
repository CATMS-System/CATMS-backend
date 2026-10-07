# patient logic, raw sql with pymysql
import re
import pymysql
from fastapi import HTTPException

from app.schemas.patient import PatientCreate
from app.services import insurance_service
from app.services.common import escape_like,lower_keys, lower_rows, transaction, write_audit

PATIENT_COLS = "Patient_ID, First_Name, Last_Name, Date_Of_Birth, Gender, NIC, Contact_Number, Email, Street_Address, City, State_Province, Postal_Code, Registration_Date, Updated_At"
EMERGENCY_COLS = "Emergency_Contact_ID, Patient_ID, First_Name, Last_Name, Relationship_To_Patient, Contact_Number, Street_Address, City, Postal_Code"

# lock=True keeps the row locked until the transaction ends (FOR UPDATE)
def get_patient_row(cursor, patient_id: int, lock: bool = False) -> dict | None:
    sql = f"SELECT {PATIENT_COLS} FROM Patient WHERE Patient_ID = %s"
    if lock:
        sql += " FOR UPDATE"
    cursor.execute(sql, (patient_id,))
    return lower_keys(cursor.fetchone())

# 3 queries: patient, emergency contacts, policies that can be used today
def get_patient_detail(conn: pymysql.Connection, patient_id: int) -> dict:
    with conn.cursor() as cursor:
        patient = get_patient_row(cursor, patient_id)
        if not patient:
            raise HTTPException(404, "Patient not found")

        cursor.execute(
            f"SELECT {EMERGENCY_COLS} FROM Emergency_Contact "
            "WHERE Patient_ID = %s ORDER BY Emergency_Contact_ID",
            (patient_id,),
        )
        patient["emergency_contacts"] = lower_rows(cursor.fetchall())
        patient["active_policies"] = insurance_service.get_policies(
            cursor, patient_id, only_active=True
        )
    return patient

def register_patient(
    conn: pymysql.Connection, data: PatientCreate, account_id: int | None = None
) -> dict:
    # everything inside is saved together or not at all
    with transaction(conn), conn.cursor() as cursor:
        # duplicate is checked by nic only, family members can share a phone number
        cursor.execute("SELECT Patient_ID FROM Patient WHERE NIC = %s", (data.nic,))
        if cursor.fetchone():
            raise HTTPException(409, "A patient with this NIC already exists")

        cursor.execute(
            "INSERT INTO Patient (First_Name, Last_Name, Date_Of_Birth, Gender, NIC, Contact_Number, Email, Street_Address, City, State_Province, Postal_Code)"
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                data.first_name,
                data.last_name,
                data.date_of_birth,
                data.gender.value,
                data.nic,
                data.contact_number,
                data.email,
                data.street_address,
                data.city,
                data.state_province,
                data.postal_code,
            ),
        )
        patient_id = cursor.lastrowid

        contact = data.emergency_contact
        cursor.execute(
            "INSERT INTO Emergency_Contact (Patient_ID, First_Name, Last_Name, Relationship_To_Patient, Contact_Number, Street_Address, City, Postal_Code)"
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                patient_id,
                contact.first_name,
                contact.last_name,
                contact.relationship_to_patient,
                contact.contact_number,
                contact.street_address,
                contact.city,
                contact.postal_code,
            ),
        )

        # optional policy goes in the same transaction
        if data.insurance_policy is not None:
            insurance_service.insert_policy(cursor, patient_id, data.insurance_policy)

        # audit only when we know who did it
        if account_id is not None:
            write_audit(
                cursor,
                account_id=account_id,
                table_name="Patient",
                record_id=patient_id,
                action="INSERT",
                new_value=get_patient_row(cursor, patient_id),
            )
    return get_patient_detail(conn, patient_id)

# a stored number can be +94771234567 or 0771234567, so search both
def get_phone_formats(number: str) -> list[str]:
    formats = [number]
    if number.startswith("+94"):
        formats.append("0" + number[3:])
    elif number.startswith("0"):
        formats.append("+94" + number[1:])
    return formats

# makes the where part of the search, matches name, nic, phone or patient id
def build_search_condition(search_text: str | None) -> tuple[str, dict]:
    text = (search_text or "").strip()
    if not text:
        # no text, match every patient
        return "1 = 1", {}

    values = {"like": f"%{escape_like(text)}%"}
    parts = [  "First_Name LIKE %(like)s",
               "Last_Name LIKE %(like)s",
               "CONCAT(First_Name, ' ', Last_Name) LIKE %(like)s",
    ]

    # only digits, so it could be a patient id
    if text.isdigit():
        parts.append("Patient_ID = %(patient_id)s")
        values["patient_id"] = int(text)

    # remove spaces and dashes so 077 123 4567 and 077-123-4567 are the same
    cleaned = re.sub(r"[\s\-]", "", text)

    # nic looks like 852140938V or 199012345678
    if re.fullmatch(r"\d{3,12}[VvXx]?", cleaned):
        parts.append("NIC LIKE %(nic)s")
        values["nic"] = f"%{cleaned}%"

    # phone number, spaces and dashes are removed from the stored number too
    if re.fullmatch(r"\+?\d{3,}", cleaned):
        for i, number in enumerate(get_phone_formats(cleaned)):
            key = f"phone{i}"
            parts.append(f"REPLACE(REPLACE(Contact_Number, ' ', ''), '-', '') LIKE %({key})s")
            values[key] = f"%{number}%"

    return "(" + " OR ".join(parts) + ")", values