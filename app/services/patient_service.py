# patient logic, raw sql with pymysql
from app.services.common import lower_keys

PATIENT_COLS = (
    "Patient_ID, First_Name, Last_Name, Date_Of_Birth, Gender, NIC, "
    "Contact_Number, Email, Street_Address, City, State_Province, "
    "Postal_Code, Registration_Date, Updated_At"
)


# lock=True keeps the row locked until the transaction ends (FOR UPDATE)
def get_patient_row(cursor, patient_id: int, lock: bool = False) -> dict | None:
    sql = f"SELECT {PATIENT_COLS} FROM Patient WHERE Patient_ID = %s"
    if lock:
        sql += " FOR UPDATE"
    cursor.execute(sql, (patient_id,))
    return lower_keys(cursor.fetchone())