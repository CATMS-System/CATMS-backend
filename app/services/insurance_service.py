# insurance providers and patient policies
from datetime import date
import pymysql
from fastapi import HTTPException

from app.schemas.patient import InsurancePolicyCreate, InsuranceProviderCreate
from app.services.common import lower_keys, lower_rows, transaction
PROVIDER_COLS = (
    "Provider_ID, Provider_Name, Contact_Number, Email, "
    "Street_Address, City, State_Province, Postal_Code"
)
# policy columns plus the provider name, so the frontend does not need a second request
POLICY_SELECT = """
    SELECT ip.Policy_ID, ip.Patient_ID, ip.Provider_ID,
           pr.Provider_Name AS provider_name, ip.Policy_Number, ip.Policy_Type,
           ip.Start_Date, ip.End_Date, ip.Default_Coverage_Percentage,
           ip.Policy_Status
    FROM Insurance_Policy ip
    JOIN Insurance_Provider pr ON pr.Provider_ID = ip.Provider_ID
"""

def get_provider(conn: pymysql.Connection, provider_id: int) -> dict:
    with conn.cursor() as cursor:
        cursor.execute(
            f"SELECT {PROVIDER_COLS} FROM Insurance_Provider WHERE Provider_ID = %s",
            (provider_id,),
        )
        row = lower_keys(cursor.fetchone())
    if not row:
        raise HTTPException(404, "Insurance provider not found")
    return row

def list_providers(conn: pymysql.Connection) -> list[dict]:
    with conn.cursor() as cursor:
        cursor.execute(f"SELECT {PROVIDER_COLS} FROM Insurance_Provider ORDER BY Provider_Name")
        return lower_rows(cursor.fetchall())
    
def create_provider(conn: pymysql.Connection, data: InsuranceProviderCreate) -> dict:
    with transaction(conn), conn.cursor() as cursor:
        # name and email must both be new
        cursor.execute(
            "SELECT Provider_ID FROM Insurance_Provider WHERE Provider_Name = %s",
            (data.provider_name,),
        )
        if cursor.fetchone():
            raise HTTPException(409, "An insurance provider with this name already exists")
        cursor.execute("SELECT Provider_ID FROM Insurance_Provider WHERE Email = %s", (data.email,))
        if cursor.fetchone():
            raise HTTPException(409, "An insurance provider with this email already exists")

        cursor.execute(
            "INSERT INTO Insurance_Provider (Provider_Name, Contact_Number, Email, "
            "Street_Address, City, State_Province, Postal_Code) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (data.provider_name,
            data.contact_number,
            data.email,
            data.street_address,
            data.city,
            data.state_province,
            data.postal_code,),)
        provider_id = cursor.lastrowid
    return get_provider(conn, provider_id)

# all policies of a patient, or only the ones that can be used today
def get_policies(cursor, patient_id: int, only_active: bool = False) -> list[dict]:
    sql = POLICY_SELECT + " WHERE ip.Patient_ID = %s"
    if only_active:
        # usable = status Active and today is between start date and end date
        sql += (
            " AND ip.Policy_Status = 'Active'"
            " AND ip.Start_Date <= CURDATE() AND ip.End_Date >= CURDATE()"
        )
    sql += " ORDER BY ip.End_Date DESC, ip.Policy_ID DESC"
    cursor.execute(sql, (patient_id,))
    return lower_rows(cursor.fetchall())

# no commit in here, the caller commits (so registration can add a policy in the same transaction)
def insert_policy(cursor, patient_id: int, data: InsurancePolicyCreate) -> int:
    # provider must exist
    cursor.execute(
        "SELECT Provider_ID FROM Insurance_Provider WHERE Provider_ID = %s", (data.provider_id,))
    if not cursor.fetchone():
        raise HTTPException(404, "Insurance provider not found")

    # policy number only has to be new for this provider, not for everyone
    cursor.execute(
        "SELECT Policy_ID FROM Insurance_Policy WHERE Provider_ID = %s AND Policy_Number = %s",
        (data.provider_id, data.policy_number),)
    if cursor.fetchone():
        raise HTTPException(409, "This provider already has a policy with that policy number")

    # a policy that already ended is saved as Expired
    policy_status = "Expired" if data.end_date < date.today() else "Active"
    cursor.execute(
        "INSERT INTO Insurance_Policy (Patient_ID, Provider_ID, Policy_Number, "
        "Policy_Type, Start_Date, End_Date, Default_Coverage_Percentage, Policy_Status) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        ( patient_id,
            data.provider_id,
            data.policy_number,
            data.policy_type.value,
            data.start_date,
            data.end_date,
            data.default_coverage_percentage,
            policy_status,),)
    return cursor.lastrowid

def get_policy(conn: pymysql.Connection, policy_id: int) -> dict:
    with conn.cursor() as cursor:
        cursor.execute(POLICY_SELECT + " WHERE ip.Policy_ID = %s", (policy_id,))
        row = lower_keys(cursor.fetchone())
    if not row:
        raise HTTPException(404, "Policy not found")
    return row