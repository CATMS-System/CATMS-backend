# patient logic, raw sql with pymysql
import pymysql
from fastapi import HTTPException

from app.schemas.patient import PatientCreate
from app.services import insurance_service
from app.services.common import lower_keys, lower_rows, transaction, write_audit

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