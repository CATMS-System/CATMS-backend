# patient logic, raw sql with pymysql
import pymysql
from fastapi import HTTPException

from app.services import insurance_service
from app.services.common import lower_keys, lower_rows

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