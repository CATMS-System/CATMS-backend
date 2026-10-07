# insurance providers and patient policies
import pymysql
from fastapi import HTTPException

from app.schemas.patient import InsuranceProviderCreate
from app.services.common import lower_keys, lower_rows, transaction
PROVIDER_COLS = (
    "Provider_ID, Provider_Name, Contact_Number, Email, "
    "Street_Address, City, State_Province, Postal_Code"
)


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